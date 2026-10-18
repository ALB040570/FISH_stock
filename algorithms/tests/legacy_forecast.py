"""Прогноз исходным приложением fish_stock_forecast (для сверки): python legacy_forecast.py <вид> <json настроек>"""
import json, os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
os.environ["FISH_SOURCE_DIR"] = str(REPO / "legacy")
sys.path.insert(0, str(REPO / "legacy" / "fish_stock_forecast"))
from app import services_forecast as sf  # noqa
from core import config
settings = json.loads(sys.argv[2])
sf.load_raw = lambda: settings
print(json.dumps(sf.results_payload(sys.argv[1]), ensure_ascii=False))
