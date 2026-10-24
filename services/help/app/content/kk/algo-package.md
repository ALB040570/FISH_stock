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
 "requires": {"datasets": ["species_props", "npc_pdu"], "steps": ["combined_stock"]},
 "parameters": [
   {"code": "PDU_CAP", "title_ru": "...", "type": "number", "default": 0.75, "category": "param", "min": 0, "max": 1},
   {"code": "species_profiles", "title_ru": "...", "type": "profile", "category": "param"},
   {"code": "species", "title_ru": "Виды", "type": "species_list", "category": "calc"}],
 "outputs": [{"code": "result", "title_ru": "...", "format": "table"}]}
```

- **Параметр санаттары**: `param` — «Алгоритм параметрлері» жиынындағы мән (атауы `fishcore.config` баптауымен сәйкес келсе, мән код жүктелгенге дейін қолданылады); `calc` — есептеудің өзінде беріледі (түрлер). Бұрынғы нұсқалардың санаттарына (`fixed`, `waterbody`, `run`) жобаларда ескертумен рұқсат етіледі.
- **Параметр түрлері**: integer, number, enum, boolean, string, species_list, year_map, species_map, species_year_map, profile.
- `requires.datasets` — деректер жиынтықтарының түрлері (соңғы нұсқалары, есептеу кезеңіне); `requires.steps` — кіріс-алгоритмдер: олардың нәтижелері кірістерде көрсетілген есептеулерден (әдепкі бойынша — негізгілерінен) беріледі.

## ctx контексі

| | |
|---|---|
| `ctx.tables` | су айдынының деректер жиынтықтары: `{түр: {"columns", "species", "rows"}}` — іске қосу сәтіндегі көшірме; `fishcore.stepkit.bundle(ctx, …)` есептеу кезеңіндегі жолдарды іріктейді |
| `ctx.params` | қадамның қорытынды параметрлері |
| `ctx.water_body`, `ctx.species_names`, `ctx.gear_kinds` | су айдыны; түр кодтары → атаулары; құралдар → seine/net |
| `ctx.load_state("<алгоритм>")` | кіріс-есептеу сақтаған объект (`ctx.save_state(obj)`); `fishcore.stepkit.need_input` — сол, түсінікті қатемен |
| `ctx.input_dir("<алгоритм>")` | кіріс-есептеу нәтижесінің каталогы |
| `ctx.add_table(code, title, columns, rows)`, `ctx.add_frame(code, title, df)` | нәтиже кестелері (дашбордтар, есептер) |
| `ctx.add_file(name, title)` → жол | нәтиже файлы (Excel, NetCDF, …) |
| `ctx.set_payload(dict)`, `ctx.metric(...)`, `ctx.note(...)` | арнайы көріністерге арналған деректер, көрсеткіштер, ескертпелер |
| `ctx.log(...)`, `ctx.progress(үлес, **info)` | журнал және орындалу барысы (бір мезгілде тоқтату да тексеріледі) |
| `raise fishrunner.UserError("...")` | пайдаланушыға түсінікті, трассировкасыз қате |

## Қадам қалай орындалады

Әр есептеу `runtime.timeout_minutes` уақыт шектеуімен жеке Python процесінде орындалады. Нәтиже есептеудің бұрынғы нәтижесін ауыстырады; кестелер, көрсеткіштер мен көріністер `result.json` файлында, күй объектісі — бұл есептеуді кіріс ретінде алатын есептеулер үшін сақталады.
