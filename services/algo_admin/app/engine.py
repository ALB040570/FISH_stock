"""
Каталог алгоритмов, параметры алгоритмов, расчёты и журнал; исполнение расчётов воркером (решение № 70).

Понятия:
- алгоритм каталога (a–k) — версии пакетов кода; включает и отключает администратор и математик;
- параметры алгоритма — именованный набор значений всех параметров одного алгоритма, с версиями; общий для водоёмов;
- расчёт — алгоритм + версия кода (пусто — последняя включённая) + водоём + период + входы (наборы данных —
  последняя версия; результаты других алгоритмов — основной расчёт водоёма или указанный) + параметры (набор и
  версия). Хранит один результат: новый запуск затирает прежний; журнал расчёта хранит, чем считали каждый раз;
- основной расчёт — один на алгоритм × водоём; мониторинг собирает картину водоёма из основных расчётов.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import socket
import sys
import zipfile
from pathlib import Path

from fishcommon.storage import Collection, atomic_write_json, dumps, locked, new_id, now_iso, read_json


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
CATALOG = build.catalog()                                    # a–k: буква, название, есть ли реализация
CATALOG_BY_CODE = {a["code"]: a for a in CATALOG}
ORDER_ALL = {a["code"]: i for i, a in enumerate(CATALOG)}
ACTIVE = ("queued", "running")
DEFAULT_SET_NAME = "По умолчанию (эталон 22.10.2026)"


def semver_key(v: str):
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


def letter(code: str) -> str:
    return (CATALOG_BY_CODE.get(code) or {}).get("letter", "")


def algo_info(E, code: str) -> dict | None:
    """Алгоритм каталога: a–k (algorithms/catalog.json) или опубликованный математиком в «Моделировании алгоритмов»."""
    a = CATALOG_BY_CODE.get(code)
    if a:
        return a
    meta = E.catalog.get(code) if code else None
    if meta:
        return {"code": code, "letter": "", "title_ru": meta.get("title_ru", code), "title_kk": meta.get("title_kk", ""),
                "planned": False, "inputs": []}
    return None


class Engine:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.catalog = Collection(self.root, "catalog")
        self.param_sets = Collection(self.root, "param_sets")
        self.calcs = Collection(self.root, "calcs")
        self.mains_path = self.root / "mains.json"
        self.migrations_path = self.root / "migrations.json"

    # ================================================================ каталог (версии кода)
    def seed_builtin(self) -> None:
        self._migrate_v3()
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
            self._seed_default_set(code, manifest, files)

    def _drop_old_builtin(self, code: str, keep: str) -> None:
        """Прежние эталонные версии другой основной версии удаляются из каталога (смена эталона, решение № 70).
        Версии, опубликованные пользователями, не трогаются; эталонные версии той же основной версии остаются."""
        cur = self.catalog.get(code) or {}
        st = dict(cur.get("versions_state", {}))
        removed = []
        for v in self.catalog.list_versions(code):
            if v.get("source") == "builtin" and str(v.get("version")).split(".")[0] != keep.split(".")[0]:
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

    # ================================================================ перенос на новую схему (один раз)
    def _migrations(self) -> dict:
        return read_json(self.migrations_path, {}) or {}

    def _migrate_v3(self) -> None:
        """Переход на каталог a–k (решение № 70, 25.10.2026): прежние запуски, цепочки расчётов и основной запуск
        удаляются (решение заказчика — пересчитать заново); алгоритмы, которых больше нет в каталоге
        («Уловистость сети и запас по уловам», «Проверки модели»), убираются; профили байесовской модели водоёмов
        становятся наборами «Параметры алгоритма i» с сохранением правок. Наборы данных и справочники — в других
        сервисах и не меняются."""
        done = self._migrations()
        if done.get("catalog_v3"):
            return
        removed = []
        for name in ("runs", "calculations"):
            d = self.root / name
            if d.exists():
                n = sum(1 for p in d.iterdir() if p.is_dir())
                shutil.rmtree(d, ignore_errors=True)
                removed.append(f"{name}: {n}")
        if (self.root / "main_runs.json").exists():
            (self.root / "main_runs.json").unlink()
            removed.append("main_runs.json")
        for code in ("stock_by_catch", "bayes_checks"):          # опубликованные пользователями — не трогаются
            if (self.catalog.dir / code).exists():
                self.catalog.purge(code)
                removed.append(f"алгоритм {code}")
        self._profiles_to_sets()
        done["catalog_v3"] = {"at": now_iso(), "removed": removed}
        atomic_write_json(self.migrations_path, done)
        if removed:
            print("[algo_admin] переход на каталог a–k: удалено — " + "; ".join(removed), flush=True)

    def _profiles_to_sets(self) -> None:
        """Профили водоёмов байесовской модели → наборы параметров алгоритма i (последняя версия профиля)."""
        pdir = self.root / "profiles"
        if not pdir.exists():
            return
        prof = Collection(self.root, "profiles")
        for p in prof.list():
            if p.get("algorithm") != "bayes_cohort" or not p.get("current_version"):
                continue
            try:
                values = json.loads(prof.read_version_file(p["id"], p["current_version"], "values.json"))
            except (OSError, ValueError):
                continue
            sp = (values or {}).get("species_profiles") or {}
            if not sp:
                continue
            wb = p.get("water_body") or ""
            name = {"zhaysan": "оз. Жайсан (профиль водоёма)"}.get(wb, f"Профиль водоёма «{wb}»")
            s = self.param_sets.create({"algorithm": "bayes_cohort", "name": name, "is_default": False, "system": False,
                                        "description": f"Перенесён из «Параметров водоёмов» ({wb}) 25.10.2026 со всеми правками",
                                        "source_water_body": wb}, actor="system")
            self.param_sets.add_version(s["id"], {"values.json": dumps({"species_profiles": sp}).encode()},
                                        {"comment": "перенос профиля водоёма (решение № 70)"}, "system")
            print(f"[algo_admin] профиль bayes_cohort / {wb} → набор параметров «{name}»", flush=True)
        shutil.rmtree(pdir, ignore_errors=True)

    # ================================================================ параметры алгоритма
    def set_values(self, sid: str, n: int | None = None) -> dict:
        s = self.param_sets.get(sid)
        n = n or s.get("current_version")
        return json.loads(self.param_sets.read_version_file(sid, n, "values.json"))

    def default_set(self, code: str) -> dict | None:
        return next((s for s in self.param_sets.list() if s.get("algorithm") == code and s.get("is_default")
                     and not s.get("deleted")), None)

    def _seed_default_set(self, code: str, manifest: dict, files: dict[str, bytes]) -> None:
        """Набор «По умолчанию» алгоритма — значения по умолчанию его манифеста (эталон). Если у новой версии кода
        значения по умолчанию другие — у набора появляется новая версия."""
        values = default_values(manifest, files)
        cur = self.default_set(code)
        if cur is None:
            cur = self.param_sets.create({"algorithm": code, "name": DEFAULT_SET_NAME, "is_default": True, "system": True,
                                          "description": "Значения по умолчанию алгоритма (эталон 22.10.2026, расчёты "
                                                         "заказчика для оз. Жайсан). Не меняется: для своих значений "
                                                         "создайте набор на его основе."}, actor="system", obj_id=f"default_{code}")
        elif cur.get("current_version") and self.set_values(cur["id"]) == values:
            return
        self.param_sets.add_version(cur["id"], {"values.json": dumps(values).encode()},
                                    {"comment": f"значения по умолчанию версии {manifest['version']}"}, "system")

    # ================================================================ основной расчёт
    def mains(self) -> dict:
        return read_json(self.mains_path, {}) or {}

    def main_of(self, water_body: str, code: str) -> str | None:
        return ((self.mains().get(water_body) or {}).get(code) or {}).get("calc_id")

    def set_main(self, water_body: str, code: str, calc_id: str | None, user_id: str, user_name: str = "") -> None:
        with locked(self.mains_path):
            data = read_json(self.mains_path, {}) or {}
            wb = data.setdefault(water_body, {})
            if calc_id is None:
                wb.pop(code, None)
            else:
                wb[code] = {"calc_id": calc_id, "set_by": user_id, "set_by_name": user_name, "set_at": now_iso()}
            atomic_write_json(self.mains_path, data)

    # ================================================================ расчёты
    def calc(self, cid: str) -> dict | None:
        c = self.calcs.get(cid)
        return None if not c or c.get("deleted") else c

    def calc_list(self) -> list[dict]:
        return [c for c in self.calcs.list() if not c.get("deleted")]

    def result_dir(self, cid: str) -> Path:
        return self.calcs.obj_dir(cid) / "result"

    def work_dir(self, cid: str) -> Path:
        return self.calcs.obj_dir(cid) / "work"

    def journal(self, cid: str) -> list[dict]:
        return read_json(self.calcs.obj_dir(cid) / "journal.json", []) or []

    def add_journal(self, cid: str, entry: dict) -> None:
        p = self.calcs.obj_dir(cid) / "journal.json"
        with locked(p):
            j = read_json(p, []) or []
            j.append({"at": now_iso(), **entry})
            atomic_write_json(p, j)

    def resolve_input(self, calc: dict, code: str) -> str | None:
        """Расчёт, который берётся входом code: указанный в расчёте или основной расчёт водоёма."""
        ref = (calc.get("inputs") or {}).get(code) or "main"
        return self.main_of(calc["water_body"], code) if ref == "main" else ref

    def update_calc(self, cid: str, **changes) -> dict:
        mp = self.calcs.obj_dir(cid) / "meta.json"
        with locked(mp):
            cur = read_json(mp)
            cur.update(changes)
            cur["heartbeat"] = now_iso()
            atomic_write_json(mp, cur)
            return cur

    def queue(self) -> list[dict]:
        rs = [c for c in self.calc_list() if c.get("state") == "queued"]
        return sorted(rs, key=lambda c: (c.get("queued_at") or "") + c["id"])

    def claim(self, worker: str) -> dict | None:
        """Следующий расчёт из очереди, у которого входы не ждут пересчёта (в очереди или выполняются)."""
        for c in self.queue():
            if self._inputs_pending(c):
                continue
            mp = self.calcs.obj_dir(c["id"]) / "meta.json"
            with locked(mp):
                cur = read_json(mp)
                if cur.get("state") != "queued":
                    continue
                cur.update(state="running", started_at=now_iso(), worker=worker, heartbeat=now_iso(), progress=None)
                atomic_write_json(mp, cur)
                return cur
        return None

    def _inputs_pending(self, c: dict) -> bool:
        return any(self.pending_input(c, code) for code in self.input_codes(c))

    def pending_input(self, c: dict, code: str) -> dict | None:
        """Расчёт-вход, который ещё в очереди или выполняется. Если основного расчёта входа нет, но расчёт этого
        алгоритма для водоёма уже поставлен в очередь, — он (его первый результат станет основным)."""
        rid = self.resolve_input(c, code)
        if rid:
            ic = self.calc(rid)
            return ic if ic and ic.get("state") in ACTIVE else None
        if ((c.get("inputs") or {}).get(code) or "main") != "main":
            return None
        return next((x for x in self.calc_list() if x["algorithm"] == code and x["water_body"] == c["water_body"]
                     and x.get("state") in ACTIVE), None)

    def input_codes(self, c: dict) -> list[str]:
        """Алгоритмы-входы расчёта (по манифесту версии кода, которой он будет выполнен)."""
        m = self.calc_manifest(c)
        return list((m or {}).get("requires", {}).get("steps", []))

    def calc_version(self, c: dict) -> str | None:
        v = c.get("version")
        if v and self.find_version(c["algorithm"], v):
            return v
        lv = self.latest_enabled(c["algorithm"])
        return lv["version"] if lv else None

    def calc_manifest(self, c: dict) -> dict | None:
        v = self.calc_version(c)
        return self.manifest(c["algorithm"], v) if v else None

    def recover_stale(self, host: str, sole: bool | None = None) -> int:
        """Расчёты «выполняется», чей воркер завершился (перезапуск, обновление), помечаются прерванными; прежний
        результат расчёта (если был) остаётся."""
        if sole is None:
            sole = os.environ.get("FISH_WORKER_SOLE", "") in ("1", "true", "yes")
        me = worker_name()
        n = 0
        for c in self.calc_list():
            if c.get("state") != "running":
                continue
            w = c.get("worker", "")
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
            msg = "Расчёт прерван (перезапуск сервера). Запустите заново."
            self.update_calc(c["id"], state="failed", finished_at=now_iso(), message=msg, progress=None)
            self.add_journal(c["id"], {"action": "run", "status": "failed", "message": msg, "by": c.get("queued_by"),
                                       "by_name": c.get("queued_by_name")})
            n += 1
        return n

    def execute(self, c: dict, clients, plan_fn, log=print) -> dict:
        """Выполнить расчёт: план (версия, параметры, входы, наборы данных) → шаг в отдельном процессе → при успехе
        результат заменяет прежний. plan_fn(c) → (план, ошибки, предупреждения)."""
        cid = c["id"]
        wdir = self.work_dir(cid)
        shutil.rmtree(wdir, ignore_errors=True)
        wdir.mkdir(parents=True)
        entry = {"action": "run", "by": c.get("queued_by"), "by_name": c.get("queued_by_name")}

        def fail(msg, **extra):
            self.add_journal(cid, {**entry, "status": "failed", "message": msg, **extra})
            return self.update_calc(cid, state="failed", finished_at=now_iso(), message=msg, progress=None)

        try:
            plan, errors, warnings = plan_fn(c)
        except Exception as e:  # noqa: BLE001
            return fail(f"Не удалось подготовить расчёт: {getattr(e, 'message', e)}")
        if errors:
            return fail("; ".join(errors))
        entry.update({k: plan[k] for k in ("version", "checksum", "param_set", "param_set_name", "param_version",
                                           "period", "datasets", "inputs")})
        try:
            tables = {t: clients.table(src["dataset_id"], src["version"]) for t, src in plan["datasets"].items()}
            (wdir / "tables.json").write_text(json.dumps(tables, ensure_ascii=False), encoding="utf-8")
            names, kinds = clients.species_names(), clients.gear_kinds()
        except Exception as e:  # noqa: BLE001
            return fail(f"Не удалось получить исходные данные: {getattr(e, 'message', e)}")
        step = wdir / "step"
        ctx = {"run_id": cid, "step": c["algorithm"], "water_body": c["water_body"], "params": plan["params"],
               "species_names": names, "gear_kinds": kinds, "period": plan["period"],
               "inputs": {code: str(self.result_dir(i["calc_id"]) / "out") for code, i in plan["inputs"].items()},
               "tables_path": str(wdir / "tables.json"), "dataset_sources": plan["datasets"]}
        executor.prepare_step(step, self.package_files(c["algorithm"], plan["version"]), ctx)
        log(f"расчёт {cid}: {c['algorithm']} {plan['version']}, водоём {c['water_body']}")
        m = self.manifest(c["algorithm"], plan["version"])
        timeout = float(m.get("runtime", {}).get("timeout_minutes", 60)) * 60

        def poll(cid=cid):
            cur = read_json(self.calcs.obj_dir(cid) / "meta.json") or {}
            self.update_calc(cid, progress=read_json(step / "progress.json"))
            return bool(cur.get("cancel_requested"))

        res = executor.run_step(step, timeout_s=timeout, on_poll=poll, poll_s=1.0)
        log_text = (step / "log.txt").read_text(encoding="utf-8") if (step / "log.txt").exists() else ""
        (self.calcs.obj_dir(cid) / "last_log.txt").write_text(log_text[-500_000:], encoding="utf-8")
        status = read_json(step / "status.json", {}) or {}
        if status.get("traceback"):
            (self.calcs.obj_dir(cid) / "last_traceback.txt").write_text(status["traceback"], encoding="utf-8")
        if res["status"] != "done":
            msg = res.get("message") or "ошибка"
            shutil.rmtree(wdir, ignore_errors=True)
            if res["status"] == "cancelled":
                self.add_journal(cid, {**entry, "status": "cancelled", "message": msg})
                return self.update_calc(cid, state="cancelled", finished_at=now_iso(), message=msg, progress=None,
                                        cancel_requested=False)
            return fail(msg, seconds=res.get("seconds"))
        result = read_json(step / "out" / "result.json", {}) or {}
        # новый результат заменяет прежний (решение № 70)
        rdir = self.result_dir(cid)
        old = rdir.with_name(".result.old")
        shutil.rmtree(old, ignore_errors=True)
        if rdir.exists():
            os.replace(rdir, old)
        os.replace(step, rdir)
        shutil.rmtree(old, ignore_errors=True)
        shutil.rmtree(wdir, ignore_errors=True)
        rid = new_id()
        info = {"result_id": rid, "finished_at": now_iso(), "seconds": res.get("seconds"),
                "years": (result.get("summary") or {}).get("years"), "notes": result.get("notes") or [],
                "metrics": result.get("metrics") or {}, "warnings": warnings, "by": c.get("queued_by"),
                "by_name": c.get("queued_by_name"), **{k: entry[k] for k in ("version", "checksum", "param_set",
                                                                              "param_set_name", "param_version",
                                                                              "period", "datasets", "inputs")}}
        if (result.get("payload") or {}).get("not_main"):          # служебный режим (подбор egg_scale, № 73)
            info["not_main"] = True
        self.add_journal(cid, {**entry, "status": "done", "message": "Расчёт выполнен", "result_id": rid,
                               "seconds": res.get("seconds"), "years": info["years"], "notes": info["notes"],
                               "warnings": warnings})
        cur = self.update_calc(cid, state="done", finished_at=info["finished_at"], message="Расчёт выполнен",
                               progress=None, result=info, cancel_requested=False)
        if not self.main_of(c["water_body"], c["algorithm"]) and not info.get("not_main"):  # первый результат — основной
            self.set_main(c["water_body"], c["algorithm"], cid, "system", "автоматически (первый результат)")
        return cur

    # ================================================================ устаревание
    def staleness(self, current_datasets: dict, water_body: str | None = None) -> dict[str, list[str]]:
        """{расчёт: причины} — результат устарел: новая версия набора данных, сменился основной расчёт-вход,
        вход пересчитан или сам устарел, изменилась версия кода (если версия не закреплена)."""
        calcs = {c["id"]: c for c in self.calc_list() if not water_body or c["water_body"] == water_body}
        memo: dict[str, list[str]] = {}

        def reasons(cid, path=()):
            if cid in memo:
                return memo[cid]
            c = calcs.get(cid) or self.calc(cid)
            if c is None or not c.get("result") or cid in path:
                memo[cid] = []
                return []
            r = c["result"]
            out = []
            cur = current_datasets.get(c["water_body"]) or {}
            for t, src in (r.get("datasets") or {}).items():
                now = cur.get(t)
                if now and (now.get("dataset_id") != src.get("dataset_id") or now.get("version") != src.get("version")):
                    out.append(f"новая версия набора данных «{t}»")
            for code, used in (r.get("inputs") or {}).items():
                rid = self.resolve_input(c, code)
                L = letter(code)
                if rid != used.get("calc_id"):
                    out.append(f"сменился основной расчёт-вход {L}" if (c.get("inputs") or {}).get(code, "main") == "main"
                               else f"сменился расчёт-вход {L}")
                    continue
                ic = calcs.get(rid) or self.calc(rid)
                if not ic or not ic.get("result"):
                    out.append(f"у расчёта-входа {L} нет результата")
                elif ic["result"].get("result_id") != used.get("result_id"):
                    out.append(f"расчёт-вход {L} пересчитан")
                elif reasons(rid, (*path, cid)):
                    out.append(f"расчёт-вход {L} устарел")
            if not c.get("version"):
                lv = self.latest_enabled(c["algorithm"])
                if lv and lv["version"] != r.get("version"):
                    out.append(f"новая версия алгоритма {lv['version']}")
            memo[cid] = out
            return out

        return {cid: reasons(cid) for cid in calcs if reasons(cid)}


def default_values(manifest: dict, files: dict[str, bytes] | None = None) -> dict:
    """Значения по умолчанию всех параметров набора (категории param и прежние fixed/waterbody/run, кроме calc)."""
    out = {}
    for p in manifest.get("parameters", []):
        if p.get("category") == "calc":
            continue
        if p.get("type") == "profile":
            prof = (files or {}).get("profiles/zhaysan.json")
            out[p["code"]] = json.loads(prof) if prof else {}
        else:
            out[p["code"]] = p.get("default")
    return out


# метка запуска процесса: в контейнере номер процесса после перезапуска тот же (1), метка — новая
_BOOT = os.urandom(4).hex()


def worker_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{_BOOT}"
