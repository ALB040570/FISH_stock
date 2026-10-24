"""
Сборка пакетов алгоритмов: algorithms/packages/<код>/ + вложенная копия fishcore → zip.

    python algorithms/build.py            # собрать все пакеты в algorithms/dist/

Сервис «Моделирование алгоритмов» при первом запуске сам собирает эти пакеты и публикует
их как проверенные версии (эталонные алгоритмы, перенесённые из fish_stock_forecast; с 3.0.0 — по одному
алгоритму каталога на пакет, решение № 70).
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGES = HERE / "packages"
# Каталог алгоритмов a–k (решение № 70): порядок букв; k — «Планируется» (без пакета, algorithms/catalog.json).
# «Проверки байесовской модели» (bayes_checks) в каталог не входят (решение № 65); пакет сохранён.
ORDER = ["net_catchability", "seine_catchability", "seine_likelihood", "net_likelihood", "seine_stock", "net_stock",
         "combined_stock", "pdu_by_age", "bayes_cohort", "forecast_pdu"]


def catalog() -> list[dict]:
    """Алгоритмы каталога a–k: буква, название, описание, есть ли реализация (algorithms/catalog.json)."""
    return json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))


def _profile_files() -> dict[str, bytes]:
    """Схема профиля байесовской модели и профиль оз. Жайсан (значения скриптов заказчика)."""
    sys.path.insert(0, str(HERE))
    from fishcore.bayes import config as bc
    run_keys = {"draws", "tune", "chains", "target_accept", "max_treedepth", "seed"}
    schema = [{**row, "category": "run" if row["key"] in run_keys else "waterbody"} for row in bc.schema_payload()]
    prof = {}
    for ru, cfg in bc.DEFAULTS.items():
        d = asdict(cfg)
        prof[bc.TOKENS[ru]] = {k: d[k] for k in bc.EDITABLE}
    return {"profile_schema.json": json.dumps(schema, ensure_ascii=False, indent=1).encode(),
            "profiles/zhaysan.json": json.dumps(prof, ensure_ascii=False, indent=1).encode()}


def package_files(code: str) -> dict[str, bytes]:
    src = PACKAGES / code
    files: dict[str, bytes] = {}
    for p in sorted(src.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            files[str(p.relative_to(src)).replace("\\", "/")] = p.read_bytes()
    for p in sorted((HERE / "fishcore").rglob("*.py")):
        if "__pycache__" not in p.parts:
            files["fishcore/" + str(p.relative_to(HERE / "fishcore")).replace("\\", "/")] = p.read_bytes()
    if code == "bayes_cohort":
        files.update(_profile_files())
    return files


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 1, 0, 0, 0))  # воспроизводимый архив
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    return buf.getvalue()


def checksum(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode())
        h.update(hashlib.sha256(files[name]).digest())
    return h.hexdigest()


def builtin() -> list[tuple[dict, dict[str, bytes]]]:
    out = []
    for code in ORDER:
        files = package_files(code)
        out.append((json.loads(files["manifest.json"]), files))
    return out


if __name__ == "__main__":
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    for manifest, files in builtin():
        name = f"{manifest['code']}-{manifest['version']}.zip"
        (dist / name).write_bytes(zip_bytes(files))
        print(name, checksum(files)[:12], len(files), "файлов")
