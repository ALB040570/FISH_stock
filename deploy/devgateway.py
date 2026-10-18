"""
Шлюз для запуска без Docker (аналог deploy/nginx.conf):
/api/<сервис>/... → http://127.0.0.1:<порт сервиса>/..., остальное — собранный фронтенд (frontend/dist).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "libs" / "fishcommon"))
from fishcommon.settings import SERVICE_PORTS  # noqa: E402

DIST = Path(os.environ.get("FISH_FRONTEND_DIST", REPO / "frontend" / "dist"))
ROUTES = {name.replace("_", "-"): f"http://127.0.0.1:{port}" for name, port in SERVICE_PORTS.items()}
HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "content-encoding", "content-length"}

app = FastAPI(title="FishStocke gateway", docs_url=None, redoc_url=None)
client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5))


@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(service: str, path: str, request: Request):
    base = ROUTES.get(service)
    if base is None or path.startswith("internal/"):
        return JSONResponse({"error": {"code": "not_found", "message": "Нет такого сервиса"}}, 404)
    url = f"{base}/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP | {"host"}}
    headers["x-forwarded-prefix"] = f"/api/{service}"
    try:
        req = client.build_request(request.method, url, params=request.query_params, headers=headers,
                                   content=await request.body())
        r = await client.send(req, stream=True)
    except httpx.ConnectError:
        return JSONResponse({"error": {"code": "service_unavailable",
                                       "message": f"Сервис «{service}» недоступен"}}, 503)
    out_headers = {k: v for k, v in r.headers.items() if k.lower() not in HOP}
    return StreamingResponse(r.aiter_raw(), status_code=r.status_code, headers=out_headers,
                             background=None)


@app.get("/{path:path}")
async def spa(path: str):
    f = DIST / path
    if path and f.is_file():
        return FileResponse(f)
    index = DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return Response("Фронтенд не собран: cd frontend && npm ci && npm run build", media_type="text/plain; charset=utf-8")
