"""
Начальная загрузка данных оз. Жайсан через API работающего приложения (после первого запуска):

    python tools/seed_zhaysan.py --url http://127.0.0.1:8080 --login admin --password <пароль> [--run stock|full]

Загружает 7 наборов данных из samples/zhaysan (данные заказчика из legacy/data_catch в шаблонах FishStocke),
создаёт расчёты по шаблонам и, по желанию, ставит расчёт в очередь.
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
    ap.add_argument("--water-body", default="zhaysan")
    ap.add_argument("--run", choices=["none", "stock", "full"], default="none")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.url.rstrip("/") + "/api", timeout=120)
    r = c.post("/users/auth/login", json={"login": a.login, "password": a.password})
    if r.status_code != 200:
        sys.exit(f"Вход не выполнен: {r.text}")
    c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    for f in sorted((REPO / "samples" / "zhaysan").glob("*.xlsx")):
        r = c.post("/data-admin/upload", data={"water_body": a.water_body, "dataset_type": f.stem, "mode": "replace",
                                                "comment": "данные заказчика (legacy/data_catch)"},
                   files={"file": (f.name, f.read_bytes())})
        j = r.json()
        print(f"{f.stem:20s} {'загружен, версия ' + str(j.get('version')) if j.get('ok') else 'ОШИБКА: ' + str(j)[:300]}")
    existing = {x["title"] for x in c.get("/algo-admin/calculations", params={"water_body": a.water_body}).json()}
    ids = {}
    for tpl in ("full", "stock"):
        r = c.post("/algo-admin/calculations/from-template", json={"water_body": a.water_body, "template": tpl})
        if r.status_code == 201:
            ids[tpl] = r.json()["id"]
            print(f"расчёт «{r.json()['title']}» создан")
    if a.run != "none" and a.run in ids:
        r = c.post(f"/algo-admin/calculations/{ids[a.run]}/run", json={})
        print("запуск поставлен в очередь:", r.json().get("id") if r.status_code == 201 else r.text)


if __name__ == "__main__":
    main()
