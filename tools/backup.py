"""
Резервное копирование и восстановление каталога данных FishStocke (запуск без Docker или внутри контейнера).

    python tools/backup.py create  --data ./data --out ./backups        # архив + список контрольных сумм
    python tools/backup.py verify  ./backups/fishstocke_20261024_0300.tar.gz
    python tools/backup.py restore ./backups/fishstocke_20261024_0300.tar.gz --data ./data

Архив содержит MANIFEST.sha256 (контрольная сумма каждого файла); восстановление проверяет их и
не перезаписывает непустой каталог без --force (текущие данные переносятся в <data>.before_restore_<время>).
Временные файлы (*.tmp, .*.tmp) и блокировки (*.lock) в архив не попадают.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import sys
import tarfile
from datetime import datetime
from pathlib import Path


def _skip(p: Path) -> bool:
    n = p.name
    return n.endswith((".lock", ".tmp")) or (n.startswith(".") and n.endswith(".tmp")) or "__pycache__" in p.parts \
        or ".pytensor" in p.parts


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def create(data: Path, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    name = out / f"fishstocke_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
    files = sorted(p for p in data.rglob("*") if p.is_file() and not _skip(p.relative_to(data)))
    lines = []
    with tarfile.open(name, "w:gz") as tar:
        for p in files:
            rel = p.relative_to(data).as_posix()
            lines.append(f"{sha(p)}  {rel}")
            tar.add(p, arcname=f"data/{rel}")
        man = ("\n".join(lines) + "\n").encode()
        info = tarfile.TarInfo("MANIFEST.sha256")
        info.size = len(man)
        tar.addfile(info, io.BytesIO(man))
    print(f"архив: {name} ({len(files)} файлов, {name.stat().st_size / 1e6:.1f} МБ)")
    return name


def verify(archive: Path) -> bool:
    with tarfile.open(archive, "r:gz") as tar:
        man = tar.extractfile("MANIFEST.sha256").read().decode().splitlines()
        want = {l.split("  ", 1)[1]: l.split("  ", 1)[0] for l in man if l.strip()}
        bad = 0
        for m in tar.getmembers():
            if not m.isfile() or not m.name.startswith("data/"):
                continue
            rel = m.name[5:]
            h = hashlib.sha256(tar.extractfile(m).read()).hexdigest()
            if want.get(rel) != h:
                print(f"не совпадает контрольная сумма: {rel}")
                bad += 1
        missing = set(want) - {m.name[5:] for m in tar.getmembers() if m.name.startswith("data/")}
        for r in missing:
            print(f"нет в архиве: {r}")
    ok = not bad and not missing
    print("архив цел" if ok else "АРХИВ ПОВРЕЖДЁН")
    return ok


def restore(archive: Path, data: Path, force: bool) -> None:
    if not verify(archive):
        sys.exit(2)
    if data.exists() and any(data.iterdir()):
        if not force:
            sys.exit(f"Каталог {data} не пуст. Остановите сервисы и повторите с --force "
                     f"(текущие данные будут перенесены в {data}.before_restore_*)")
        keep = data.with_name(f"{data.name}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.move(str(data), keep)
        print(f"текущие данные перенесены в {keep}")
    data.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        for m in tar.getmembers():
            if m.isfile() and m.name.startswith("data/") and ".." not in Path(m.name).parts:
                target = data / m.name[5:]
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as f:
                    f.write(tar.extractfile(m).read())
    print(f"восстановлено в {data}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("--data", default="data"); c.add_argument("--out", default="backups")
    v = sub.add_parser("verify"); v.add_argument("archive")
    r = sub.add_parser("restore"); r.add_argument("archive"); r.add_argument("--data", default="data"); r.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd == "create":
        create(Path(a.data), Path(a.out))
    elif a.cmd == "verify":
        sys.exit(0 if verify(Path(a.archive)) else 2)
    else:
        restore(Path(a.archive), Path(a.data), a.force)


if __name__ == "__main__":
    main()
