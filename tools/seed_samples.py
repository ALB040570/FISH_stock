"""
Загрузка данных заказчика в работающее приложение (после первого запуска):

    python tools/seed_samples.py --password <пароль>                       # все водоёмы из samples/
    python tools/seed_samples.py --password <пароль> --water-body zhaysan --run stock

Для каждого водоёма (папка samples/<код водоёма>) загружает 7 наборов данных (данные заказчика из
legacy/data_catch в шаблонах FishStock), создаёт расчёты алгоритмов каталога (stock — a–h, full — a–j; решение
№ 66) с параметрами «По умолчанию» и, по желанию, ставит их в очередь (зависимые ждут свои входы).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

CHAIN = ["net_catchability", "seine_catchability", "seine_likelihood", "net_likelihood", "seine_stock", "net_stock",
         "combined_stock", "pdu_by_age", "bayes_cohort", "forecast_pdu"]

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
        # расчёты алгоритмов каталога (решение № 66): stock — a–h (запас по уловам и ПДУ НПЦ в штуках),
        # full — ещё модель i и прогноз j; параметры «По умолчанию», входы — основные расчёты водоёма
        chain = CHAIN[:8] if a.run in ("stock", "none") else CHAIN
        r = c.get("/algo-admin/calcs", params={"water_body": wb})
        if r.status_code != 200:
            errors += 1
            print(f"ОШИБКА: список расчётов недоступен ({r.status_code})")
            continue
        have = {x["algorithm"]: x for x in r.json()}
        for code in chain:
            x = have.get(code)
            if x is None:
                r = c.post("/algo-admin/calcs", json={"algorithm": code, "water_body": wb})
                if r.status_code != 201:
                    errors += 1
                    print(f"ОШИБКА: расчёт {code} не создан: {r.text[:300]}")
                    break
                x = r.json()
                print(f"расчёт «{x['title']}» создан")
            if a.run != "none" and x.get("state") not in ("queued", "running"):
                r = c.post(f"/algo-admin/calcs/{x['id']}/run")
                print(f"  в очередь: {'да' if r.status_code == 200 else r.text[:300]}")
    if errors:
        sys.exit(f"Ошибок: {errors}. Повторный запуск загрузит данные заново (новой версией).")


if __name__ == "__main__":
    main()
