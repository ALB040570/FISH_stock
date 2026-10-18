"""
Сохранение результатов этапа 2 в NetCDF под теми же именами и в тех же форматах,
что файлы в data_stock исходного проекта (чтобы следующие этапы и старые скрипты
могли их читать). xarray импортируется только здесь.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .catch import HaulCatch
from .catchability_net import CUBE_NAME as NET_CUBE_NAME, NetCatchability
from .stock import GEARS, MEAN, METHODS, VARIANTS, StockResult

GEAR_TOKEN = {config.GEAR_NET: "net", config.GEAR_SEINE: "seine", MEAN: "combined"}


def _less(ages):
    return [f"less_{int(a)}" for a in ages]


def _column(s: pd.Series) -> np.ndarray:
    """Числа — как есть, текст — массив object из str (так пишет и старый проект)."""
    if pd.api.types.is_numeric_dtype(s):
        return s.to_numpy()
    return s.astype(str).to_numpy().astype(object)


def haul_da(hc: HaulCatch, arr: np.ndarray, name: str):
    import xarray as xr
    m = hc.meta
    da = xr.DataArray(arr, dims=["Id", "FishType", "LessAge"],
                      coords={"Id": m["Id"].to_numpy(), "FishType": hc.species, "LessAge": _less(hc.ages)}, name=name)
    coords = {c: ("Id", _column(m[c])) for c in m.columns if c != "Id"}
    return da.assign_coords(**coords, age=("LessAge", hc.ages.astype(int)))


def cube_da(years, species, ages, arr: np.ndarray, name: str):
    import xarray as xr
    da = xr.DataArray(arr, dims=["Year", "FishType", "LessAge"],
                      coords={"Year": list(years), "FishType": list(species), "LessAge": _less(ages)}, name=name)
    return da.assign_coords(age=("LessAge", np.asarray(ages).astype(int)))


def save_stage2(res: StockResult, net_c: NetCatchability, results_dir: Path | None = None) -> dict[str, str]:
    results_dir = Path(results_dir or config.RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    wb = res.waterbody
    saved: dict[str, str] = {}

    # CSV — всегда
    p = results_dir / f"{wb}_catchability_net_params.csv"
    net_c.params_frame().to_csv(p, index=False, encoding="utf-8-sig"); saved["net_params_csv"] = str(p)
    p = results_dir / f"{wb}_stock_totals.csv"
    res.totals_frame().to_csv(p, index=False, encoding="utf-8-sig"); saved["totals_csv"] = str(p)

    try:
        import xarray  # noqa: F401
    except ImportError:
        saved["nc_error"] = "не установлен xarray"
        return saved

    files = {}
    for gear in GEARS:
        hc = res.catches[gear]
        files[f"{wb}_catch_{GEAR_TOKEN[gear]}_3d.nc"] = haul_da(hc, hc.values, "catch_volume")
        for v in VARIANTS:
            files[f"{wb}_stock_{GEAR_TOKEN[gear]}_{v}_3d.nc"] = haul_da(hc, res.per_haul[(gear, v)], "stock")
    files[f"{wb}_catchability_net_3d.nc"] = cube_da(res.years, res.species, res.ages, net_c.cube(), NET_CUBE_NAME)
    for gear in (*GEARS, MEAN):
        for v in VARIANTS:
            for meth in METHODS:
                files[f"{wb}_yearly_stock_{GEAR_TOKEN[gear]}_{v}_{meth}_3d.nc"] = cube_da(
                    res.years, res.species, res.ages, res.yearly[(gear, v, meth)], "yearly_stock")

    errors = []
    for name, da in files.items():
        try:
            da.to_netcdf(results_dir / name, engine="netcdf4")
        except Exception as e:  # например, не установлен netCDF4
            errors.append(f"{name}: {e}")
    saved["nc_files"] = str(len(files) - len(errors))
    if errors:
        saved["nc_error"] = errors[0] if len(errors) == 1 else f"{len(errors)} файлов не записано: {errors[0]}"
    return saved


def load_old_cube(filename: str, old_dir: Path | None = None):
    """Старый куб (Year, FishType, LessAge) из data_stock: dict {(вид, год): {группа: значение}} или None."""
    path = Path(old_dir or config.OLD_DATA_STOCK_DIR) / filename
    if not path.exists():
        return None
    try:
        import xarray as xr
    except ImportError:
        return None
    with xr.open_dataarray(path) as da:
        da = da.load()
    if "age" in da.coords:
        ages = da["age"].values.astype(int)
    else:
        ages = np.array([int(str(s).split("_")[1]) for s in da["LessAge"].values])
    out = {}
    for year in da["Year"].values:
        for fish in da["FishType"].values:
            vals = da.sel(Year=year, FishType=fish).values.astype(float)
            out[(str(fish), int(year))] = dict(zip(ages.tolist(), vals.tolist()))
    return out


def save_pdu(pdu, results_dir: Path | None = None) -> dict[str, str]:
    """ПДУ НПЦ в штуках по возрастам (Year × FishType × LessAge) и сводная таблица."""
    results_dir = Path(results_dir or config.RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}
    p = results_dir / f"{pdu.waterbody}_pdu_summary.csv"
    pdu.summary_frame().to_csv(p, index=False, encoding="utf-8-sig")
    saved["pdu_csv"] = str(p)
    try:
        da = cube_da(pdu.years, pdu.species, pdu.ages, pdu.pieces, "pdu_pieces")
    except ImportError:
        saved["nc_error"] = "не установлен xarray"
        return saved
    try:
        name = f"{pdu.waterbody}_pdu_pieces_3d.nc"
        da.attrs.update({"units": "штук",
                         "method": "раздел 5 статьи; окончательный запас (сеть+невод); итерации до исчерпания квоты"})
        da.to_netcdf(results_dir / name, engine="netcdf4")
        saved["nc_files"] = "1"
    except Exception as e:
        saved["nc_error"] = str(e)
    return saved
