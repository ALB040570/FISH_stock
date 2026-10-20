# Пакет алгоритма: manifest.json и ctx

Алгоритм — пакет файлов:

```
manifest.json      описание: код, версия, параметры, требуемые данные и шаги, результаты
algorithm.py       точка входа: def run(ctx)
<модули>.py        любой дополнительный код (эталонные пакеты содержат копию расчётного ядра fishcore)
```

## manifest.json

```json
{"code": "my_method", "version": "1.0.0", "title_ru": "...", "title_kk": "...", "description": "...",
 "entrypoint": "algorithm:run", "runtime": {"python": ">=3.11", "timeout_minutes": 30},
 "requires": {"datasets": ["catches", "npc_pdu"], "steps": ["stock_by_catch"]},
 "parameters": [
   {"code": "PDU_CAP", "title_ru": "...", "type": "number", "default": 0.75, "category": "fixed", "min": 0, "max": 1},
   {"code": "species_profiles", "title_ru": "...", "type": "profile", "category": "waterbody"},
   {"code": "horizon", "title_ru": "...", "type": "integer", "default": 5, "category": "run", "min": 1, "max": 10}],
 "outputs": [{"code": "result", "title_ru": "...", "format": "table"}]}
```

- **Категории параметров**: `fixed` — неизменяемые (если имя совпадает с настройкой `fishcore.config`, значение применяется до загрузки кода); `waterbody` — из профиля водоёма; `run` — задаются в расчёте.
- **Типы параметров**: integer, number, enum, boolean, string, species_list, year_map, species_map, species_year_map, profile.
- `requires.datasets` — типы наборов данных; `requires.steps` — предыдущие шаги цепочки.

## Контекст ctx

| | |
|---|---|
| `ctx.tables` | наборы данных водоёма: `{тип: {"columns", "species", "rows"}}` — снимок на момент запуска |
| `ctx.params` | итоговые параметры шага |
| `ctx.water_body`, `ctx.species_names`, `ctx.gear_kinds` | водоём; коды видов → названия; орудия → seine/net |
| `ctx.load_state("<шаг>")` | объект, сохранённый предыдущим шагом (`ctx.save_state(obj)`) |
| `ctx.input_dir("<шаг>")` | каталог результатов предыдущего шага |
| `ctx.add_table(code, title, columns, rows)`, `ctx.add_frame(code, title, df)` | таблицы результата (дашборды, отчёты) |
| `ctx.add_file(name, title)` → путь | файл результата (Excel, NetCDF, …) |
| `ctx.set_payload(dict)`, `ctx.metric(...)`, `ctx.note(...)` | данные для особых представлений, показатели, примечания |
| `ctx.log(...)`, `ctx.progress(доля, **info)` | журнал и ход выполнения (заодно проверяется отмена) |
| `raise fishrunner.UserError("...")` | понятная пользователю ошибка без трассировки |

## Как выполняется шаг

Каждый шаг запускается в отдельном процессе Python с ограничением времени из `runtime.timeout_minutes`. Результаты шага записываются в его каталог запуска; таблицы, показатели и представления сохраняются в `result.json`, объект состояния — для следующих шагов.
