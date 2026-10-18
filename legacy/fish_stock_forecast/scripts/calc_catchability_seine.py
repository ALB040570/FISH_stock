"""
Расчёт уловистости невода из командной строки (без веб-интерфейса).

    python -m scripts.calc_catchability_seine

Сохраняет results/zhaysan_catchability_seine_3d.nc (формат как в старом проекте),
results/zhaysan_catchability_seine_params.csv и results/zhaysan_catchability_seine.xlsx,
печатает параметры и сравнение с прежними байесовскими коэффициентами.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from core import config
from core.catchability_seine import compute_seine_catchability, load_old_cube, save_results


def main():
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_rows", 200)

    print(f"Исходные данные: {config.DATA_CATCH_DIR}")
    res = compute_seine_catchability()
    saved = save_results(res)

    params = res.params_frame()
    cols = ["вид", "год", "a (крутизна)", "j50 (МНК)", "j50 (правило статьи)", "Z (общая смертность)",
            "c(2)", "c(m1)", "R² (лог)", "рыб в пробе", "статус"]
    print(params[cols].round(3).to_string(index=False))

    xlsx = config.RESULTS_DIR / f"{res.waterbody}_catchability_seine.xlsx"
    try:
        from app.services import _state, seine_excel
        _state["result"] = res
        _state["old"] = load_old_cube()
        xlsx.write_bytes(seine_excel())
        saved["xlsx"] = xlsx
    except Exception as e:
        print(f"Excel не записан: {e}")

    old = load_old_cube()
    if old is not None:
        print("\nСравнение с прежними (байесовскими) коэффициентами, средняя |разница| по возрастам 2..m1:")
        rows = []
        for (fish, year), r in res.fits.items():
            prev = old.get((fish, year))
            if prev is None:
                continue
            diff = [abs(c - prev.get(int(a), np.nan)) for a, c in zip(r.ages, r.catchability)]
            rows.append({"вид": fish, "год": year, "|Δc| среднее": np.nanmean(diff), "|Δc| макс": np.nanmax(diff)})
        if rows:
            cmp = pd.DataFrame(rows).groupby("вид", sort=False)[["|Δc| среднее", "|Δc| макс"]].mean()
            print(cmp.round(3).to_string())
    else:
        print("\nПрежние коэффициенты не прочитаны (нужны xarray и netCDF4).")

    print("\nСохранено:")
    for k, v in saved.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
