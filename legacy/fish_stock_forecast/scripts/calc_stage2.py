"""
Этап 2 из командной строки: улов по ловам, уловистость сети (парабола), запас по уловам.

    python -m scripts.calc_stage2

Сохраняет в results/ файлы .nc под теми же именами, что в data_stock исходного проекта,
и печатает сверку с прежними результатами (нужны xarray и netCDF4).
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from core import config
from core.catchability_seine import compute_seine_catchability, save_results
from core.data_source import load_fish_props
from core.export_nc import GEAR_TOKEN, load_old_cube, save_pdu, save_stage2
from core.pdu_npc import compute_pdu
from core.stock import GEARS, MEAN, METHODS, VARIANTS, compute_stock


def old_totals(res, gear, variant, method):
    cube = load_old_cube(f"{res.waterbody}_yearly_stock_{GEAR_TOKEN[gear]}_{variant}_{method}_3d.nc")
    if cube is None:
        return None
    out = np.full((len(res.years), len(res.species)), np.nan)
    for yi, y in enumerate(res.years):
        for si, s in enumerate(res.species):
            vals = cube.get((s, y))
            if vals:
                arr = np.array([vals.get(a, np.nan) for a in range(2, res.m1[s] + 1)], float)
                out[yi, si] = np.nansum(arr) if not np.all(np.isnan(arr)) else np.nan
    return out


def main():
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    print(f"Исходные данные: {config.DATA_CATCH_DIR}")

    seine_c = compute_seine_catchability()
    save_results(seine_c)
    res, net_c, _ = compute_stock(seine_c=seine_c)
    saved = save_stage2(res, net_c)
    pdu = compute_pdu(res, load_fish_props())
    saved.update({f"pdu_{k}": v for k, v in save_pdu(pdu).items()})

    # --- уловистость сети ---
    params = net_c.params_frame()
    print("\nУловистость сети (парабола), нарушений ограничений (24):",
          int(params["статус"].str.contains("нарушено").sum()))
    old_net = load_old_cube(f"{res.waterbody}_catchability_net_3d.nc")
    if old_net:
        rows = []
        for (fish, year), r in net_c.fits.items():
            prev = old_net.get((fish, year))
            if prev:
                d = [abs(c - prev.get(int(a), np.nan)) for a, c in zip(r.ages, r.catchability)]
                rows.append({"вид": fish, "|Δc| среднее": np.nanmean(d), "|Δc| макс": np.nanmax(d)})
        print("Сравнение с прежними коэффициентами сети (колокол):")
        print(pd.DataFrame(rows).groupby("вид", sort=False).mean().round(3).to_string())

    # --- годовой запас ---
    print("\nГодовой запас, млн шт (уловистость по возрастам, «по запасам»):")
    for si, fish in enumerate(res.species):
        tab = pd.DataFrame({
            "сеть": res.yearly_total(config.GEAR_NET, "with_ages", "on_stock")[:, si],
            "невод": res.yearly_total(config.GEAR_SEINE, "with_ages", "on_stock")[:, si],
            "окончательный (сеть+невод)": res.yearly_total(MEAN, "with_ages", "on_stock")[:, si],
            "НПЦ": res.npc_stock[:, si] if res.npc_stock is not None else np.nan,
        }, index=res.years) / 1e6
        print(f"\n  {fish}")
        print(tab.T.round(2).to_string())

    # --- ПДУ по возрастам ---
    summ = pdu.summary_frame()
    print("\nПДУ НПЦ по возрастам (медиана по годам):")
    print(summ.groupby("вид", sort=False)[["ПДУ НПЦ, т", "распределено, т", "не распределено, т",
                                          "ПДУ / биомасса, %", "итераций"]].median().round(2).to_string())

    # --- сверка с прежними годовыми оценками ---
    rows = []
    for gear in GEARS:
        for v in VARIANTS:
            for meth in METHODS:
                old = old_totals(res, gear, v, meth)
                if old is None:
                    continue
                new = res.yearly_total(gear, v, meth)
                with np.errstate(divide="ignore", invalid="ignore"):
                    ratio = new / old
                for si, fish in enumerate(res.species):
                    rows.append({"орудие": gear, "вариант": v, "метод": meth, "вид": fish,
                                 "новый / прежний (медиана по годам)": np.nanmedian(ratio[:, si])})
    if rows:
        cmp = pd.DataFrame(rows).pivot_table(index="вид", columns=["орудие", "вариант", "метод"],
                                             values="новый / прежний (медиана по годам)", sort=False)
        print("\nНовый годовой запас / прежний (медиана по годам):")
        print(cmp.round(2).to_string())
    else:
        print("\nПрежние годовые оценки не прочитаны (нужны xarray и netCDF4).")

    print("\nСохранено:")
    for k, v in saved.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
