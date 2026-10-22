"""
Загрузка данных заказчика в работающее приложение (после первого запуска):

    python tools/seed_samples.py --password <пароль>                       # все водоёмы из samples/
    python tools/seed_samples.py --password <пароль> --water-body zhaysan --run stock

Для каждого водоёма (папка samples/<код водоёма>) загружает 7 наборов данных (данные заказчика из
legacy/data_catch в шаблонах FishStock), создаёт расчёты по шаблонам и, по желанию, ставит расчёт в очередь.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--login", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--water-body", default="all", help="код водоёма или all — все папки samples/")
    ap.add_argument("--run", choices=["none", "stock", "full"], default="none")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.url.rstrip("/") + "/api", timeout=120)
    r = c.post("/users/auth/login", json={"login": a.login, "password": a.password})
    if r.status_code != 200:
        sys.exit(f"Вход не выполнен: {r.text}")
    c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    wbs = sorted(p.name for p in (REPO / "samples").iterdir() if p.is_dir()) if a.water_body == "all" else [a.water_body]
    errors = 0
    for wb in wbs:
        print(f"== {wb}")
        for f in sorted((REPO / "samples" / wb).glob("*.xlsx")):
            r = c.post("/data-admin/upload", data={"water_body": wb, "dataset_type": f.stem, "mode": "replace",
                                                    "comment": "данные заказчика (legacy/data_catch)"},
                       files={"file": (f.name, f.read_bytes())})
            try:
                j = r.json()
            except ValueError:
                j = {"status": r.status_code, "text": r.text[:200]}
            errors += not j.get("ok")
            print(f"{f.stem:20s} {'загружен, версия ' + str(j.get('version')) if j.get('ok') else 'ОШИБКА: ' + str(j)[:300]}")
        if errors:
            continue  # расчёты — только для водоёмов с полностью загруженными данными
        prefix = {"full": "Полный расчёт ПДУ", "stock": "Запас по уловам"}
        r = c.get("/algo-admin/calculations", params={"water_body": wb})
        if r.status_code != 200:
            errors += 1
            print(f"ОШИБКА: список расчётов недоступен ({r.status_code})")
            continue
        ids = {tpl: x["id"] for x in r.json()
               for tpl, p in prefix.items() if x["title"].startswith(p)}
        for tpl in ("full", "stock"):
            if tpl in ids:
                continue
            r = c.post("/algo-admin/calculations/from-template", json={"water_body": wb, "template": tpl})
            if r.status_code == 201:
                ids[tpl] = r.json()["id"]
                print(f"расчёт «{r.json()['title']}» создан")
        if a.run != "none" and a.run in ids:
            r = c.post(f"/algo-admin/calculations/{ids[a.run]}/run", json={})
            print("запуск поставлен в очередь:", r.json().get("id") if r.status_code == 201 else r.text)
    if errors:
        sys.exit(f"Ошибок: {errors}. Повторный запуск загрузит данные заново (новой версией).")


if __name__ == "__main__":
    main()
