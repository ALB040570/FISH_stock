"""
Веб-приложение «Запасы рыб»: FastAPI + HTML-страницы с SVG-графиками.

Запуск из корня проекта:
    uvicorn app.main:app --reload
и открыть http://127.0.0.1:8000
"""
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import cache, config
from app import jobs, services, services_bayes, services_forecast, services_overview, services_stock
from core.bayes.config import DEFAULTS as BAYES_SPECIES, TOKENS as BAYES_TOKENS

APP_DIR = Path(__file__).resolve().parent

def _warmup():
    """Этапы 1–3 при запуске сервера (из кэша — за секунды), чтобы первая страница открывалась сразу."""
    try:
        with cache.timed("сервер готов: этапы 1–3 загружены"):
            services_stock.get_pdu()
    except Exception as e:  # noqa: BLE001 — ошибку покажет страница при обращении
        cache.log(f"этапы 1–3 не загружены при запуске: {type(e).__name__}: {e}")


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_warmup, name="warmup", daemon=True).start()
    yield


class SlowRequestLog:
    """Пишет в консоль запросы дольше секунды — чтобы было видно, что тормозит."""

    def __init__(self, app, threshold: float = 1.0):
        self.app, self.threshold = app, threshold

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        t0 = time.perf_counter()
        try:
            await self.app(scope, receive, send)
        finally:
            dt = time.perf_counter() - t0
            if dt >= self.threshold:
                seconds = f"{dt:.1f}".replace(".", ",")
                cache.log(f"запрос {scope.get('method', '')} {scope.get('path', '')}: {seconds} с")


app = FastAPI(title="Запасы рыб — оценка, прогноз, ПДУ", version="0.1.0", lifespan=lifespan)
app.add_middleware(SlowRequestLog)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

# Боковое меню: страницы по шагам расчёта
NAV = [
    {"title": None, "entries": [
        {"href": "/", "title": "Обзор", "num": "⌂", "key": None},
    ]},
    {"title": "Данные и запас", "entries": [
        {"href": "/catchability/seine", "title": "Уловистость невода", "num": 1, "key": "seine"},
        {"href": "/catchability/net", "title": "Уловистость сети", "num": 2, "key": "stock"},
        {"href": "/stock", "title": "Запас по уловам", "num": 3, "key": "stock"},
        {"href": "/pdu", "title": "ПДУ по возрастам", "num": 4, "key": "stock"},
    ]},
    {"title": "Модель", "entries": [
        {"href": "/bayes", "title": "Байесовская модель", "num": 5, "key": "bayes"},
    ]},
    {"title": "Результат", "entries": [
        {"href": "/forecast", "title": "Прогноз и ПДУ", "num": 6, "key": "bayes"},
    ]},
]
N_STEPS = 6


def _nav(active: str) -> tuple[list, str | None]:
    """Меню с отметками состояния шагов и подпись «Шаг N из 6» для текущей страницы."""
    n_bayes = sum(1 for sp in BAYES_SPECIES if services_bayes.R.result_path(sp, "new").exists())
    status = {
        "seine": ("✓", "ok") if services._state["result"] is not None else ("…", ""),
        "stock": ("✓", "ok") if services_stock._state["stock"] is not None else ("…", ""),
        "bayes": (f"{n_bayes}/{len(BAYES_SPECIES)}", "ok" if n_bayes == len(BAYES_SPECIES) else "warn"),
    }
    groups, step = [], None
    for g in NAV:
        entries = []
        for e in g["entries"]:
            st, cls = status.get(e["key"], ("", ""))
            entries.append({**e, "status": st, "status_class": cls})
            if e["href"] == active and isinstance(e["num"], int):
                step = f"Шаг {e['num']} из {N_STEPS}"
        groups.append({"title": g["title"], "entries": entries})
    return groups, step


def _page(request: Request, template: str, active: str, **ctx):
    nav, step = _nav(active)
    return templates.TemplateResponse(
        request, template,
        {"nav": nav, "active": active, "step_label": step, "waterbody": config.WATERBODY,
         "source_dir": str(config.SOURCE_PROJECT_DIR), **ctx},
    )


@app.get("/", response_class=HTMLResponse)
def overview_page(request: Request):
    """Обзор: сводка по видам и состояние шагов расчёта."""
    return _page(request, "overview.html", active="/")


@app.get("/api/overview")
def overview_data():
    return services_overview.overview_payload()


# ---------------------------------------------------------------------------
# Уловистость невода
# ---------------------------------------------------------------------------
@app.get("/catchability/seine", response_class=HTMLResponse)
def seine_page(request: Request):
    return _page(request, "catchability_seine.html", active="/catchability/seine")


@app.get("/api/catchability/seine")
def seine_data():
    """Параметры сигмоид, коэффициенты и уловы по всем видам и годам."""
    return services.seine_payload()


@app.post("/api/catchability/seine/recalculate")
def seine_recalculate():
    """Пересчитать по исходным данным (data_catch) и сохранить в results/."""
    services.recalculate()
    return services.seine_payload()


@app.get("/api/catchability/seine/export.xlsx")
def seine_export():
    content = services.seine_excel()
    filename = f"{config.WATERBODY}_catchability_seine.xlsx"
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _xlsx(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Уловистость сети (парабола, формулы (22)-(24))
# ---------------------------------------------------------------------------
@app.get("/catchability/net", response_class=HTMLResponse)
def net_page(request: Request):
    return _page(request, "catchability_net.html", active="/catchability/net")


@app.get("/api/catchability/net")
def net_data():
    return services_stock.net_payload()


@app.get("/api/catchability/net/export.xlsx")
def net_export():
    return _xlsx(services_stock.net_excel(), f"{config.WATERBODY}_catchability_net.xlsx")


# ---------------------------------------------------------------------------
# Запас по уловам: сеть (балансовый), невод (27), годовой запас, окончательный (сеть+невод)
# ---------------------------------------------------------------------------
@app.get("/stock", response_class=HTMLResponse)
def stock_page(request: Request):
    return _page(request, "stock.html", active="/stock")


@app.get("/api/stock")
def stock_data():
    return services_stock.stock_payload()


@app.post("/api/stock/recalculate")
def stock_recalculate():
    """Пересчитать этап 2 (уловы, уловистость сети, запас) по исходным данным."""
    services_stock.recalculate()
    return services_stock.stock_payload()


@app.get("/api/stock/export.xlsx")
def stock_export():
    return _xlsx(services_stock.stock_excel(), f"{config.WATERBODY}_stock_by_catch.xlsx")


# ---------------------------------------------------------------------------
# ПДУ НПЦ по возрастам (раздел 5 статьи)
# ---------------------------------------------------------------------------
@app.get("/pdu", response_class=HTMLResponse)
def pdu_page(request: Request):
    return _page(request, "pdu.html", active="/pdu")


@app.get("/api/pdu")
def pdu_data():
    return services_stock.pdu_payload()


@app.get("/api/pdu/export.xlsx")
def pdu_export():
    return _xlsx(services_stock.pdu_excel(), f"{config.WATERBODY}_pdu_by_age.xlsx")


# ---------------------------------------------------------------------------
# Байесовская когортная модель (уравнения (16)-(17) статьи)
# ---------------------------------------------------------------------------
def _species(name: str) -> str:
    """Вид по названию или латинскому обозначению (lesh, sudak, …)."""
    by_token = {v: k for k, v in BAYES_TOKENS.items()}
    sp = by_token.get(name, name)
    if sp not in BAYES_SPECIES:
        raise HTTPException(404, f"неизвестный вид: {name}")
    return sp


@app.get("/bayes", response_class=HTMLResponse)
def bayes_page(request: Request):
    return _page(request, "bayes.html", active="/bayes")


@app.get("/api/bayes/overview")
def bayes_overview():
    """Виды, настройки (скрипт / текущие), наличие результатов, состояние фонового расчёта."""
    return services_bayes.overview()


@app.post("/api/bayes/config/{species}")
async def bayes_config_save(species: str, request: Request):
    """Сохранить настройки вида (тело — JSON {ключ: значение}); в файл пишутся отличия от скрипта."""
    sp = _species(species)
    values = await request.json()
    try:
        return services_bayes.save_config(sp, values)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/bayes/config/{species}/reset")
def bayes_config_reset(species: str):
    return services_bayes.reset_config(_species(species))


@app.post("/api/bayes/prior/{species}")
def bayes_prior(species: str):
    """Априорная проверка: динамика по выборкам из априорных распределений (секунды, без PyMC)."""
    return services_bayes.run_prior(_species(species))


@app.post("/api/bayes/run")
async def bayes_run(request: Request):
    """Запустить расчёт в фоне. Тело: {"species": ["окунь", …], "mode": "new" | "check"}."""
    body = await request.json()
    species = [_species(s) for s in body.get("species", [])]
    try:
        return services_bayes.start_job(species, body.get("mode", "new"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.get("/api/bayes/status")
def bayes_status():
    return jobs.status() or {"state": "none"}


@app.post("/api/bayes/cancel")
def bayes_cancel():
    return jobs.cancel() or {"state": "none"}


@app.get("/api/bayes/results/{species}")
def bayes_results(species: str, source: str = "new"):
    """Результаты вида: source = new (новый расчёт), check (сверка), prior (априорная проверка)."""
    try:
        return services_bayes.results_payload(_species(species), source)
    except KeyError as e:
        raise HTTPException(404, f"нет такого источника: {e}")


@app.get("/api/bayes/export.xlsx")
def bayes_export(species: str, source: str = "new"):
    sp = _species(species)
    try:
        content = services_bayes.results_excel(sp, source)
    except FileNotFoundError:
        raise HTTPException(404, "расчёт ещё не выполнен")
    return _xlsx(content, f"{config.WATERBODY}_bayes_{BAYES_TOKENS[sp]}_{source}.xlsx")


# ---------------------------------------------------------------------------
# Прогноз запаса на 1–10 лет и ПДУ (этап 5)
# ---------------------------------------------------------------------------
@app.get("/forecast", response_class=HTMLResponse)
def forecast_page(request: Request):
    return _page(request, "forecast.html", active="/forecast")


@app.get("/api/forecast/settings")
def forecast_settings():
    """Горизонт, k, площади водоёма по годам, смертность и фиксированный ПДУ по видам."""
    return services_forecast.settings_payload()


@app.post("/api/forecast/settings")
async def forecast_settings_save(request: Request):
    try:
        return services_forecast.save_settings(await request.json())
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/forecast/settings/reset")
def forecast_settings_reset():
    return services_forecast.reset_settings()


@app.get("/api/forecast/summary")
def forecast_summary():
    """Сводка по всем видам: ПДУ первого прогнозного года, численность в конце прогноза, вероятность снижения."""
    return services_forecast.summary_payload()


@app.get("/api/forecast/results/{species}")
def forecast_results(species: str):
    return services_forecast.results_payload(_species(species))


@app.get("/api/forecast/export.xlsx")
def forecast_export():
    return _xlsx(services_forecast.excel(), f"{config.WATERBODY}_forecast.xlsx")
