"""
Каталог версий алгоритмов, профили водоёмов, расчёты (цепочки) и запуски; исполнение запусков воркером.
"""
from __future__ import annotations

import io
import json
import os
import socket
import sys
import time
import zipfile
from pathlib import Path

from fishcommon.storage import Collection, atomic_write_json, dumps, locked, now_iso, read_json

def _algorithms_dir() -> Path:
    """Каталог пакетов алгоритмов: FISH_ALGORITHMS_DIR; в образе Docker — /srv/algorithms (рядом с app/);
    в копии репозитория — <репозиторий>/algorithms (services/<сервис>/app → на три уровня выше)."""
    if os.environ.get("FISH_ALGORITHMS_DIR"):
        return Path(os.environ["FISH_ALGORITHMS_DIR"])
    here = Path(__file__).resolve()
    candidates = [here.parents[1] / "algorithms"]
    if len(here.parents) > 3:
        candidates.append(here.parents[3] / "algorithms")
    candidates.append(Path("/srv/algorithms"))
    return next((c for c in candidates if (c / "build.py").exists()), candidates[-1])


REPO_ALGOS = _algorithms_dir()
sys.path.insert(0, str(REPO_ALGOS))
import build  # noqa: E402
import executor  # noqa: E402

STEP_ORDER = {c: i for i, c in enumerate(build.ORDER)}
TERMINAL = ("done", "failed", "cancelled")


def semver_key(v: str):
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


class Engine:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.catalog = Collection(self.root, "catalog")
        self.profiles = Collection(self.root, "profiles")
        self.calculations = Collection(self.root, "calculations")
        self.runs = Collection(self.root, "runs")

    # ================================================================ каталог
    def seed_builtin(self) -> None:
        for manifest, files in build.builtin():
            code = manifest["code"]
            if not self.catalog.exists(code):
                self.catalog.create({"code": code, "title_ru": manifest["title_ru"], "title_kk": manifest.get("title_kk", ""),
                                     "description": manifest.get("description", ""), "versions_state": {}}, actor="system",
                                     obj_id=code)
            if not self.find_version(code, manifest["version"]):
                self.publish(manifest, files, actor="system", source="builtin",
                             report={"status": "passed", "note": "эталонный алгоритм; проверен на контрольных примерах оз. Жайсан (эталон 22.10.2026)"})
            self._drop_old_builtin(code, manifest["version"])
            prof = files.get("profiles/zhaysan.json")
            if prof and not self.profiles.exists(f"{code}__zhaysan"):
                self.save_profile(code, "zhaysan", {"species_profiles": json.loads(prof)}, "system",
                                  "значения расчётов заказчика для оз. Жайсан")
                self.profiles.update(self.profile_id(code, "zhaysan"), {"migrated_to": f"defaults {manifest['version']}"},
                                     actor="system")
            elif prof and files.get("previous_defaults_1.0.json"):
                self._migrate_profiles(code, json.loads(prof), json.loads(files["previous_defaults_1.0.json"]),
                                       manifest["version"])

    def _migrate_profiles(self, code: str, new: dict, previous: dict, version: str) -> None:
        """Профили водоёмов после смены эталона (23.10.2026): значение, совпадающее с прежним значением по
        умолчанию, заменяется новым значением по умолчанию; значения, изменённые пользователями, сохраняются;
        параметров, которых больше нет в модели, в профиле не остаётся. Каждый профиль получает новую версию
        (прежняя — в истории профиля). Выполняется один раз на версию алгоритма."""
        tag = f"defaults {version}"
        for p in self.profiles.list():
            if p.get("algorithm") != code or p.get("migrated_to") == tag:
                continue
            cur = self.get_profile(code, p["water_body"])
            if not cur:
                continue
            old_sp = (cur.get("values") or {}).get("species_profiles") or {}
            out = {}
            keys = set(next(iter(new.values()), {}))
            for sp, vals in old_sp.items():
                vals = vals or {}
                if sp not in new:                          # вид не из эталона: только убрать исчезнувшие параметры
                    out[sp] = {k: v for k, v in vals.items() if k in keys}
                    continue
                merged = dict(new[sp])
                for k, v in vals.items():
                    if k in merged and k in previous.get(sp, {}) and v != previous[sp][k]:
                        merged[k] = v                      # изменено пользователем — сохраняем
                out[sp] = merged
            self.profiles.add_version(self.profile_id(code, p["water_body"]),
                                      {"values.json": dumps({**(cur.get("values") or {}), "species_profiles": out}).encode()},
                                      {"comment": f"переход на эталон 22.10.2026 (версия алгоритма {version}): новые значения "
                                                  "по умолчанию, изменения пользователей сохранены"}, "system")
            self.profiles.update(self.profile_id(code, p["water_body"]), {"migrated_to": tag}, actor="system")
            print(f"[algo_admin] профиль {code} / {p['water_body']}: переведён на значения версии {version}", flush=True)

    def _drop_old_builtin(self, code: str, keep: str) -> None:
        """Прежние эталонные версии удаляются из каталога (решение заказчика 23.10.2026: новый эталон).
        Запуски по ним остаются: в запуске хранятся версия, параметры и результаты. Версии, опубликованные
        пользователями, не трогаются."""
        import shutil
        cur = self.catalog.get(code) or {}
        st = dict(cur.get("versions_state", {}))
        removed = []
        for v in self.catalog.list_versions(code):
            if v.get("source") == "builtin" and v.get("version") != keep:
                shutil.rmtree(self.catalog.version_dir(code, v["n"]), ignore_errors=True)
                st.pop(v.get("version"), None)
                removed.append(v.get("version"))
        if removed:
            self.catalog.update(code, {"versions_state": st}, actor="system")
            print(f"[algo_admin] {code}: удалены прежние эталонные версии {', '.join(removed)}", flush=True)

    def publish(self, manifest: dict, files: dict[str, bytes], actor: str, source: str, report: dict | None = None) -> dict:
        code = manifest["code"]
        if not self.catalog.exists(code):
            self.catalog.create({"code": code, "title_ru": manifest["title_ru"], "title_kk": manifest.get("title_kk", ""),
                                 "description": manifest.get("description", ""), "versions_state": {}}, actor=actor,
                                 obj_id=code)
        if self.find_version(code, manifest["version"]):
            raise ValueError(f"Версия {manifest['version']} алгоритма {code} уже опубликована")
        checksum = build.checksum(files)
        info = {"version": manifest["version"], "checksum": checksum, "source": source, "report": report or {},
                "title_ru": manifest["title_ru"]}
        v = self.catalog.add_version(code, {"package.zip": build.zip_bytes(files),
                                            "manifest.json": json.dumps(manifest, ensure_ascii=False).encode()}, info, actor)
        cur = self.catalog.get(code)
        st = cur.get("versions_state", {})
        st[manifest["version"]] = {"enabled": True, "n": v["n"]}
        self.catalog.update(code, {"versions_state": st, "title_ru": manifest["title_ru"],
                                   "description": manifest.get("description", "")}, actor=actor)
        return v

    def find_version(self, code: str, version: str) -> dict | None:
        if not self.catalog.exists(code):
            return None
        for v in self.catalog.list_versions(code):
            if v.get("version") == version:
                return v
        return None

    def versions(self, code: str) -> list[dict]:
        cur = self.catalog.get(code) or {}
        st = cur.get("versions_state", {})
        out = []
        for v in self.catalog.list_versions(code):
            out.append({**v, "enabled": st.get(v["version"], {}).get("enabled", True),
                        "manifest": self.manifest(code, v["version"])})
        return sorted(out, key=lambda v: semver_key(v["version"]), reverse=True)

    def latest_enabled(self, code: str) -> dict | None:
        for v in self.versions(code):
            if v["enabled"]:
                return v
        return None

    def manifest(self, code: str, version: str) -> dict:
        v = self.find_version(code, version)
        return json.loads(self.catalog.read_version_file(code, v["n"], "manifest.json"))

    def package_files(self, code: str, version: str) -> dict[str, bytes]:
        v = self.find_version(code, version)
        data = self.catalog.read_version_file(code, v["n"], "package.zip")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}

    def package_zip(self, code: str, version: str) -> bytes:
        v = self.find_version(code, version)
        return self.catalog.read_version_file(code, v["n"], "package.zip")

    def set_enabled(self, code: str, version: str, enabled: bool, actor: str) -> None:
        cur = self.catalog.get(code)
        st = cur.get("versions_state", {})
        st.setdefault(version, {})["enabled"] = enabled
        self.catalog.update(code, {"versions_state": st}, actor=actor)

    # ================================================================ профили водоёмов
    def profile_id(self, code: str, water_body: str) -> str:
        return f"{code}__{water_body}"

    def get_profile(self, code: str, water_body: str) -> dict | None:
        pid = self.profile_id(code, water_body)
        p = self.profiles.get(pid)
        if not p or not p.get("current_version"):
            return None
        values = json.loads(self.profiles.read_version_file(pid, p["current_version"], "values.json"))
        return {**p, "values": values}

    def save_profile(self, code: str, water_body: str, values: dict, actor: str, comment: str = "") -> dict:
        pid = self.profile_id(code, water_body)
        if not self.profiles.exists(pid):
            self.profiles.create({"algorithm": code, "water_body": water_body}, actor=actor, obj_id=pid)
        self.profiles.add_version(pid, {"values.json": dumps(values).encode()}, {"comment": comment}, actor)
        return self.get_profile(code, water_body)

    def profile_version_values(self, code: str, water_body: str, n: int) -> dict:
        return json.loads(self.profiles.read_version_file(self.profile_id(code, water_body), n, "values.json"))

    # ================================================================ запуски
    def run_dir(self, run_id: str) -> Path:
        return self.runs.obj_dir(run_id)

    def step_dir(self, run_id: str, i: int, code: str) -> Path:
        return self.run_dir(run_id) / "steps" / f"{i + 1:02d}_{code}"

    def queue(self) -> list[dict]:
        rs = [r for r in self.runs.list() if r.get("status") == "queued"]
        return sorted(rs, key=lambda r: r["created_at"] + r["id"])

    def claim(self, worker: str) -> dict | None:
        for r in self.queue():
            mp = self.runs.obj_dir(r["id"]) / "meta.json"
            with locked(mp):
                cur = read_json(mp)
                if cur.get("status") != "queued":
                    continue
                cur.update(status="running", started_at=now_iso(), worker=worker, heartbeat=now_iso())
                atomic_write_json(mp, cur)
                return cur
        return None

    def update_run(self, run_id: str, **changes) -> dict:
        mp = self.runs.obj_dir(run_id) / "meta.json"
        with locked(mp):
            cur = read_json(mp)
            cur.update(changes)
            cur["heartbeat"] = now_iso()
            atomic_write_json(mp, cur)
            return cur

    def recover_stale(self, host: str, sole: bool | None = None) -> int:
        """Запуски «выполняется», чей воркер завершился (перезапуск, обновление), помечаются прерванными.

        sole — этот процесс единственный воркер каталога данных (Docker: один контейнер worker; run_local — один
        процесс; переменная FISH_WORKER_SOLE=1). Тогда при старте воркера все «выполняется» — от прежних процессов,
        даже если имя хоста другое (контейнер пересоздан при обновлении — у него новое имя хоста).
        Без sole проверяются только запуски этого хоста: процесс жив и это не мы с тем же номером процесса
        (в контейнере номер процесса после перезапуска снова 1 — отличаем по метке запуска процесса).
        """
        if sole is None:
            sole = os.environ.get("FISH_WORKER_SOLE", "") in ("1", "true", "yes")
        me = worker_name()
        n = 0
        for r in self.runs.list():
            if r.get("status") != "running":
                continue
            w = r.get("worker", "")
            if w == me:
                continue
            parts = w.split(":")
            if not sole:
                if parts[0] != host:
                    continue
                pid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                alive = False
                if pid and pid != os.getpid():
                    try:
                        os.kill(pid, 0)
                        alive = True
                    except OSError:
                        alive = False
                if alive:
                    continue
            self.update_run(r["id"], status="failed", finished_at=now_iso(),
                            message="Расчёт прерван (перезапуск сервера). Запустите заново.")
            n += 1
        return n

    def execute(self, run: dict, clients, log=print) -> dict:
        """Выполнить запуск: снимок данных → шаги цепочки по порядку."""
        run_id = run["id"]
        rdir = self.run_dir(run_id)
        inputs = rdir / "inputs"
        inputs.mkdir(exist_ok=True)
        try:
            tables = {}
            for dtype, src in run["datasets"].items():
                tables[dtype] = clients.table(src["dataset_id"], src["version"])
            (inputs / "tables.json").write_text(json.dumps(tables, ensure_ascii=False), encoding="utf-8")
            names, kinds = clients.species_names(), clients.gear_kinds()
            atomic_write_json(inputs / "dictionaries.json", {"species_names": names, "gear_kinds": kinds})
        except Exception as e:  # noqa: BLE001
            return self.update_run(run_id, status="failed", finished_at=now_iso(),
                                   message=f"Не удалось получить исходные данные: {getattr(e, 'message', e)}")
        steps = run["steps"]
        done_dirs: dict[str, Path] = {}
        for i, st in enumerate(steps):
            meta = read_json(rdir / "meta.json")
            if meta.get("cancel_requested"):
                for j in range(i, len(steps)):
                    steps[j]["status"] = "cancelled"
                return self.update_run(run_id, status="cancelled", finished_at=now_iso(), steps=steps,
                                       message="Расчёт отменён пользователем")
            if st.get("skip"):
                src = st.get("reuse_from")
                if src:
                    done_dirs[st["algorithm"]] = Path(src)
                st["status"] = "reused"
                self.update_run(run_id, steps=steps)
                continue
            d = self.step_dir(run_id, i, st["algorithm"])
            ctx = {"run_id": run_id, "step": st["algorithm"], "water_body": run["water_body"], "params": st["params"],
                   "species_names": names, "gear_kinds": kinds,
                   "inputs": {k: str(v / "out") for k, v in done_dirs.items()},
                   "tables_path": str(inputs / "tables.json"), "dataset_sources": run["datasets"]}
            executor.prepare_step(d, self.package_files(st["algorithm"], st["version"]), ctx)
            st.update(status="running", started_at=now_iso(), dir=str(d.relative_to(rdir)))
            self.update_run(run_id, steps=steps, current_step=i)
            log(f"запуск {run_id}: шаг {i + 1}/{len(steps)} {st['algorithm']} {st['version']}")
            m = self.manifest(st["algorithm"], st["version"])
            timeout = float(m.get("runtime", {}).get("timeout_minutes", 60)) * 60

            def poll(run_id=run_id):
                cur = read_json(self.runs.obj_dir(run_id) / "meta.json") or {}
                self.update_run(run_id)  # heartbeat
                return bool(cur.get("cancel_requested"))

            res = executor.run_step(d, timeout_s=timeout, on_poll=poll, poll_s=1.0)
            st.update(status=res["status"], finished_at=now_iso(), message=res.get("message"),
                      seconds=res.get("seconds"))
            if res["status"] != "done":
                for j in range(i + 1, len(steps)):
                    steps[j]["status"] = "skipped"
                status = "cancelled" if res["status"] == "cancelled" else "failed"
                return self.update_run(run_id, status=status, finished_at=now_iso(), steps=steps,
                                       message=f"Шаг «{st['title']}»: {res.get('message') or 'ошибка'}")
            done_dirs[st["algorithm"]] = d
            self.update_run(run_id, steps=steps)
        return self.update_run(run_id, status="done", finished_at=now_iso(), steps=steps, message="Расчёт выполнен")


# метка запуска процесса: в контейнере номер процесса после перезапуска тот же (1), метка — новая
_BOOT = os.urandom(4).hex()


def worker_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{_BOOT}"
