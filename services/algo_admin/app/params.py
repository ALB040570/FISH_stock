"""Проверка и сборка параметров шага по манифесту: неизменяемые → водоём (профиль) → запуск."""
from __future__ import annotations


def _num(v, kind):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise ValueError
    f = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
    if kind == "integer":
        if f != int(f):
            raise ValueError
        return int(f)
    return f


def check_value(p: dict, v, species_codes: set[str] | None = None):
    """Возвращает (значение, ошибка)."""
    t, title = p.get("type"), p.get("title_ru") or p["code"]
    if v is None or v == "" or v == [] or v == {}:
        return (None if t not in ("year_map", "species_map", "species_year_map") else {}), None
    try:
        if t in ("integer", "number"):
            out = _num(v, t)
            if p.get("min") is not None and out < p["min"]:
                return None, f"«{title}»: не меньше {p['min']}"
            if p.get("max") is not None and out > p["max"]:
                return None, f"«{title}»: не больше {p['max']}"
            return out, None
        if t == "enum":
            allowed = [e["value"] for e in p.get("enum", [])]
            if v not in allowed:
                return None, f"«{title}»: допустимо {', '.join(map(str, allowed))}"
            return v, None
        if t == "boolean":
            return bool(v), None
        if t == "string":
            return str(v), None
        if t == "species_list":
            vals = [str(x) for x in (v if isinstance(v, list) else str(v).split(","))]
            vals = [x.strip() for x in vals if x.strip()]
            if species_codes is not None:
                bad = [x for x in vals if x not in species_codes]
                if bad:
                    return None, f"«{title}»: неизвестные виды {', '.join(bad)}"
            return vals, None
        if t == "year_map":
            out = {}
            for y, x in dict(v).items():
                yy = int(y)
                xv = _num(x, "number")
                if xv is not None:
                    if xv <= 0:
                        return None, f"«{title}», {yy}: положительное число"
                    out[str(yy)] = xv
            return out, None
        if t == "species_map":
            out = {}
            for s, x in dict(v).items():
                xv = _num(x, "number")
                if xv is not None:
                    if xv < 0:
                        return None, f"«{title}», {s}: неотрицательное число"
                    out[s] = xv
            return out, None
        if t == "species_year_map":
            out = {}
            for s, years in dict(v).items():
                inner = {}
                for y, x in dict(years or {}).items():
                    xv = _num(x, "number")
                    if xv is not None:
                        if not 0 < xv < 1:
                            return None, f"«{title}», {s} {y}: доля от 0 до 1"
                        inner[str(int(y))] = xv
                if inner:
                    out[s] = inner
            return out, None
        if t == "profile":
            if not isinstance(v, dict):
                return None, f"«{title}»: ожидается набор значений по видам"
            return v, None
    except (TypeError, ValueError):
        return None, f"«{title}»: неверное значение «{v}»"
    return v, None


def merge(manifest: dict, profile_values: dict | None, run_values: dict | None, species_codes=None):
    """Итоговые параметры шага и ошибки. Неизменяемые параметры нельзя задавать в расчёте/запуске."""
    out, errors = {}, []
    run_values = dict(run_values or {})
    profile_values = dict(profile_values or {})
    for p in manifest.get("parameters", []):
        code, cat = p["code"], p.get("category", "run")
        if cat == "fixed":
            if code in run_values and run_values[code] not in (None, "") and run_values[code] != p.get("default"):
                errors.append(f"«{p.get('title_ru', code)}» — неизменяемый параметр методики; меняется только новой версией алгоритма")
            out[code] = p.get("default")
            run_values.pop(code, None)
            continue
        if cat == "waterbody":
            raw = profile_values.get(code, p.get("default"))
        else:
            raw = run_values.get(code, p.get("default"))
        v, err = check_value(p, raw, species_codes)
        if err:
            errors.append(err)
        if p.get("required") and v in (None, {}, []):
            errors.append(f"«{p.get('title_ru', code)}»: обязательный параметр")
        out[code] = v
    known = {p["code"] for p in manifest.get("parameters", [])}
    for k in run_values:
        if k not in known:
            errors.append(f"Неизвестный параметр «{k}»")
    return out, errors
