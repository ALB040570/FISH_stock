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
 "requires": {"datasets": ["species_props", "npc_pdu"], "steps": ["combined_stock"]},
 "parameters": [
   {"code": "PDU_CAP", "title_ru": "...", "type": "number", "default": 0.75, "category": "param", "min": 0, "max": 1},
   {"code": "species_profiles", "title_ru": "...", "type": "profile", "category": "param"},
   {"code": "species", "title_ru": "Виды", "type": "species_list", "category": "calc"}],
 "outputs": [{"code": "result", "title_ru": "...", "format": "table"}]}
```

- **Категории параметров**: `param` — значение из набора «Параметры алгоритма» (если имя совпадает с настройкой `fishcore.config`, значение применяется до загрузки кода); `calc` — задаётся в самом расчёте (виды). Категории прежних версий (`fixed`, `waterbody`, `run`) допускаются в черновиках с предупреждением.
- **Типы параметров**: integer, number, enum, boolean, string, species_list, year_map, species_map, species_year_map, profile.
- `requires.datasets` — типы наборов данных (последние версии, за период расчёта); `requires.steps` — алгоритмы-входы: их результаты передаются из расчётов, указанных во входах (по умолчанию — основных).

## Контекст ctx

| | |
|---|---|
| `ctx.tables` | наборы данных водоёма: `{тип: {"columns", "species", "rows"}}` — снимок на момент запуска; `fishcore.stepkit.bundle(ctx, …)` отбирает строки за период расчёта |
| `ctx.params` | итоговые параметры шага |
| `ctx.water_body`, `ctx.species_names`, `ctx.gear_kinds` | водоём; коды видов → названия; орудия → seine/net |
| `ctx.load_state("<алгоритм>")` | объект, сохранённый расчётом-входом (`ctx.save_state(obj)`); `fishcore.stepkit.need_input` — то же с понятной ошибкой |
| `ctx.input_dir("<алгоритм>")` | каталог результата расчёта-входа |
| `ctx.add_table(code, title, columns, rows)`, `ctx.add_frame(code, title, df)` | таблицы результата (дашборды, отчёты) |
| `ctx.add_file(name, title)` → путь | файл результата (Excel, NetCDF, …) |
| `ctx.set_payload(dict)`, `ctx.metric(...)`, `ctx.note(...)` | данные для особых представлений, показатели, примечания |
| `ctx.log(...)`, `ctx.progress(доля, **info)` | журнал и ход выполнения (заодно проверяется отмена) |
| `raise fishrunner.UserError("...")` | понятная пользователю ошибка без трассировки |

## Как выполняется шаг

Каждый расчёт выполняется в отдельном процессе Python с ограничением времени из `runtime.timeout_minutes`. Результат заменяет прежний результат расчёта; таблицы, показатели и представления сохраняются в `result.json`, объект состояния — для расчётов, которые берут этот расчёт входом.
