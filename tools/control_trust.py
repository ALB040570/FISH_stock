"""Независимый пересчёт контрольного примера «Можно ли верить запасу» (Жайсан) по файлам эталона 22.10.2026.

    cd legacy/fish_stock_forecast/results && python ../../../tools/control_trust.py 2024
"""

import sys, numpy as np, pandas as pd, xarray as xr
Y = int(sys.argv[1]) if len(sys.argv) > 1 else 2024
cs = xr.open_dataset("zhaysan_catchability_seine_3d.nc")["corrected_catchability_coefficient_seine"]
cn = xr.open_dataset("zhaysan_catchability_net_3d.nc")["corrected_catchability_coefficient"]
fin = xr.open_dataset("zhaysan_yearly_stock_combined_with_ages_on_stock_3d.nc")["yearly_stock"]
tot = pd.read_csv("zhaysan_stock_totals.csv"); tot = tot[(tot["вариант"] == "с учётом возрастов") & tot["метод"].str.startswith("по запасам")]
sp = pd.read_csv("zhaysan_catchability_seine_params.csv")
npar = pd.read_csv("zhaysan_catchability_net_params.csv")
ages = list(cs["age"].values)
props_cbar = {}
out = []
for fish in cs["FishType"].values:
    fish = str(fish)
    c_s = cs.sel(Year=Y, FishType=fish).values; c_n = cn.sel(Year=Y, FishType=fish).values
    N = fin.sel(Year=Y, FishType=fish).values; Np = fin.sel(Year=Y - 1, FishType=fish).values if Y - 1 in fin["Year"].values else None
    prow = sp[(sp["вид"] == fish) & (sp["год"] == Y)].iloc[0]
    cbar_net = float(npar[(npar["вид"] == fish) & (npar["год"] == Y)].iloc[0][[c for c in npar.columns if "задан" in c][0]])
    m1 = int(prow["m1"]); valid = [i for i, a in enumerate(ages) if a <= m1]
    flagged = []
    for k, i in enumerate(valid):
        lo = 0.01 if k == 0 else 0.1
        if not np.isnan(c_s[i]) and (abs(c_s[i] - lo) <= (1e-4 if k == 0 else 1e-3) or abs(c_s[i] - 0.8) <= 1e-3):
            flagged.append(ages[i])
        if not np.isnan(c_n[i]) and c_n[i] > 0 and (abs(c_n[i] - cbar_net / 3) <= 1e-3 or abs(c_n[i] - 0.8) <= 1e-3):
            if ages[i] not in flagged: flagged.append(ages[i])
    Nv = np.nan_to_num(N); total = Nv[valid].sum()
    b = sum(Nv[ages.index(a)] for a in flagged) / total * 100 if total else np.nan
    t = tot[(tot["вид"] == fish) & (tot["год"] == Y)].iloc[0]
    ratio = t["невод, шт"] / t["сеть, шт"] if t["сеть, шт"] else np.nan
    k = n = 0; best = None
    if Np is not None:
        for i in valid:
            a = ages[i]
            if a - 1 in ages and Np[ages.index(a - 1)] and Np[ages.index(a - 1)] > 0 and not np.isnan(N[i]):
                x = N[i] / Np[ages.index(a - 1)]; n += 1; k += x > 2
                if best is None or x > best[0]: best = (x, a)
    out.append(dict(вид=fish, bounds=round(b, 1), ages=",".join(f"{a-1}–{a}" for a in sorted(flagged)), ratio=round(ratio, 2),
                    cohorts=f"{k}/{n}", best=round(best[0], 1) if best else None, n=int(prow["рыб в пробе"]), r2=round(prow["R² (лог)"], 2),
                    pooled="за все годы" in str(prow["статус"]) or "все годы" in str(prow.get("статус", "")), stock=total))
df = pd.DataFrame(out).sort_values("stock", ascending=False).drop(columns="stock")
print(df.to_string(index=False))
