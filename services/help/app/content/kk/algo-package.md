# Алгоритм пакеті: manifest.json және ctx

Алгоритм — файлдар пакеті:

```
manifest.json      сипаттама: код, нұсқа, параметрлер, қажетті деректер мен қадамдар, нәтижелер
algorithm.py       кіру нүктесі: def run(ctx)
<модульдер>.py     кез келген қосымша код (эталондық пакеттерде fishcore есептеу ядросының көшірмесі бар)
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

- **Параметр санаттары**: `fixed` — өзгермейтін (атауы `fishcore.config` баптауымен сәйкес келсе, мән код жүктелгенге дейін қолданылады); `waterbody` — су айдынының профилінен; `run` — есептеуде беріледі.
- **Параметр түрлері**: integer, number, enum, boolean, string, species_list, year_map, species_map, species_year_map, profile.
- `requires.datasets` — деректер жиынтықтарының түрлері; `requires.steps` — тізбектің алдыңғы қадамдары.

## ctx контексі

| | |
|---|---|
| `ctx.tables` | су айдынының деректер жиынтықтары: `{түр: {"columns", "species", "rows"}}` — іске қосу сәтіндегі көшірме |
| `ctx.params` | қадамның қорытынды параметрлері |
| `ctx.water_body`, `ctx.species_names`, `ctx.gear_kinds` | су айдыны; түр кодтары → атаулары; құралдар → seine/net |
| `ctx.load_state("<қадам>")` | алдыңғы қадам сақтаған объект (`ctx.save_state(obj)`) |
| `ctx.input_dir("<қадам>")` | алдыңғы қадам нәтижелерінің каталогы |
| `ctx.add_table(code, title, columns, rows)`, `ctx.add_frame(code, title, df)` | нәтиже кестелері (дашбордтар, есептер) |
| `ctx.add_file(name, title)` → жол | нәтиже файлы (Excel, NetCDF, …) |
| `ctx.set_payload(dict)`, `ctx.metric(...)`, `ctx.note(...)` | арнайы көріністерге арналған деректер, көрсеткіштер, ескертпелер |
| `ctx.log(...)`, `ctx.progress(үлес, **info)` | журнал және орындалу барысы (бір мезгілде тоқтату да тексеріледі) |
| `raise fishrunner.UserError("...")` | пайдаланушыға түсінікті, трассировкасыз қате |

## Қадам қалай орындалады

Әр қадам `runtime.timeout_minutes` уақыт шектеуімен жеке Python процесінде іске қосылады. Қадам нәтижелері іске қосудағы оның каталогына жазылады; кестелер, көрсеткіштер мен көріністер `result.json` файлында, күй объектісі — келесі қадамдар үшін сақталады.
