"""
Проверка значений по описанию поля справочника / столбца набора данных.

Описание поля:
    {"code", "title_ru", "title_kk", "type", "required", "unit", "min", "max",
     "enum": [{"value", "title_ru", "title_kk"}], "ref_entity", "system"}
Типы: string, text, integer, number, boolean, date, enum, ref, geo_point, geo_shape.

Пропуск (None, пустая строка, NaN) остаётся пропуском: в ноль не превращается.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime

TYPES = ("string", "text", "integer", "number", "boolean", "date", "enum", "ref", "geo_point", "geo_shape")

TYPE_TITLES = {
    "string": "Строка", "text": "Текст", "integer": "Целое число", "number": "Число",
    "boolean": "Да/нет", "date": "Дата", "enum": "Список значений", "ref": "Ссылка на справочник",
    "geo_point": "Точка на карте", "geo_shape": "Контур на карте",
}

CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def is_missing(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def _num(v):
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    return float(s)


def coerce(field: dict, v, ref_values: dict | None = None):
    """Приводит значение к типу поля. Возвращает (значение, ошибка|None)."""
    t = field.get("type", "string")
    title = field.get("title_ru") or field.get("code")
    if is_missing(v):
        if field.get("required"):
            return None, f"«{title}»: обязательное поле не заполнено"
        return None, None
    try:
        if t in ("string", "text"):
            out = str(v).strip()
            mx = field.get("max_length")
            if mx and len(out) > mx:
                return None, f"«{title}»: не длиннее {mx} символов"
        elif t == "integer":
            f = _num(v)
            if math.isnan(f) or f != int(f):
                return None, f"«{title}»: нужно целое число, получено «{v}»"
            out = int(f)
        elif t == "number":
            out = _num(v)
            if math.isnan(out) or math.isinf(out):
                return None, f"«{title}»: нужно число, получено «{v}»"
        elif t == "boolean":
            if isinstance(v, bool):
                out = v
            else:
                s = str(v).strip().lower()
                if s in ("1", "да", "иә", "true", "yes", "1.0"):
                    out = True
                elif s in ("0", "нет", "жоқ", "false", "no", "0.0"):
                    out = False
                else:
                    return None, f"«{title}»: нужно «да» или «нет», получено «{v}»"
        elif t == "date":
            if isinstance(v, datetime):
                out = v.date().isoformat()
            elif isinstance(v, date):
                out = v.isoformat()
            else:
                s = str(v).strip()
                for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%Y-%m-%d %H:%M:%S"):
                    try:
                        out = datetime.strptime(s, fmt).date().isoformat()
                        break
                    except ValueError:
                        continue
                else:
                    return None, f"«{title}»: дата должна быть в виде ДД.ММ.ГГГГ, получено «{v}»"
        elif t == "enum":
            allowed = field.get("enum") or []
            s = str(v).strip()
            match = None
            for e in allowed:
                cands = {str(e.get("value")).lower(), str(e.get("title_ru", "")).lower(), str(e.get("title_kk", "")).lower()}
                if s.lower() in cands:
                    match = e.get("value")
                    break
            if match is None:
                vals = ", ".join(str(e.get("title_ru") or e.get("value")) for e in allowed)
                return None, f"«{title}»: значение «{v}» не из списка ({vals})"
            out = match
        elif t == "ref":
            s = str(v).strip()
            refs = ref_values or {}
            key = refs.get(s.lower())
            if key is None:
                ent = field.get("ref_entity")
                return None, f"«{title}»: «{v}» нет в справочнике «{ent}»"
            out = key
        elif t == "geo_point":
            if isinstance(v, (list, tuple)) and len(v) == 2:
                lat, lon = float(v[0]), float(v[1])
            else:
                parts = re.split(r"[;\s]+", str(v).strip().replace(",", " "))
                lat, lon = float(parts[0]), float(parts[1])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None, f"«{title}»: координаты вне допустимых пределов"
            out = [round(lat, 6), round(lon, 6)]
        elif t == "geo_shape":
            if not isinstance(v, dict) or v.get("type") not in ("Polygon", "MultiPolygon"):
                return None, f"«{title}»: контур должен быть многоугольником GeoJSON"
            out = v
        else:
            return None, f"«{title}»: неизвестный тип поля {t}"
    except (TypeError, ValueError, IndexError):
        names = {"integer": "целое число", "number": "число", "geo_point": "координаты «широта, долгота»"}
        return None, f"«{title}»: нужно {names.get(t, t)}, получено «{v}»"
    if t in ("integer", "number"):
        lo, hi = field.get("min"), field.get("max")
        if lo is not None and out < lo:
            return None, f"«{title}»: значение {out} меньше допустимого {lo}"
        if hi is not None and out > hi:
            return None, f"«{title}»: значение {out} больше допустимого {hi}"
    return out, None


def validate_field_def(f: dict) -> list[str]:
    errs = []
    code = f.get("code", "")
    if not CODE_RE.match(code or ""):
        errs.append(f"Код поля «{code}»: латинские строчные буквы, цифры и _, начинается с буквы")
    if f.get("type") not in TYPES:
        errs.append(f"Поле «{code}»: неизвестный тип «{f.get('type')}»")
    if not (f.get("title_ru") or "").strip():
        errs.append(f"Поле «{code}»: нужно название на русском")
    if f.get("type") == "enum" and not f.get("enum"):
        errs.append(f"Поле «{code}»: для списка значений нужны значения")
    if f.get("type") == "ref" and not f.get("ref_entity"):
        errs.append(f"Поле «{code}»: укажите справочник для ссылки")
    lo, hi = f.get("min"), f.get("max")
    if lo is not None and hi is not None and lo > hi:
        errs.append(f"Поле «{code}»: минимум больше максимума")
    return errs


def validate_record(fields: list[dict], values: dict, refs: dict[str, dict] | None = None):
    """Проверка записи справочника. refs: {ref_entity: {нижний регистр ключа/названия: id}}."""
    out, errors = {}, []
    for f in fields:
        v, err = coerce(f, values.get(f["code"]), (refs or {}).get(f.get("ref_entity") or ""))
        if err:
            errors.append({"field": f["code"], "message": err})
        out[f["code"]] = v
    unknown = set(values) - {f["code"] for f in fields}
    for u in sorted(unknown):
        errors.append({"field": u, "message": f"Неизвестное поле «{u}»"})
    return out, errors
