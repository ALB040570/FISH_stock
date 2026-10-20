"""
docs/install.md — раздел «Установка и сопровождение» справки одним файлом (для тех, кто ставит приложение
и ещё не может войти в него). Источник — статьи справки services/help/app/content/ru.

    python tools/gen_install_doc.py
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "services" / "help" / "app" / "content"


def build(lang: str = "ru") -> str:
    spec = importlib.util.spec_from_file_location("help_export", REPO / "services/help/app/export.py")
    ex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex)
    secs = {s["code"]: s for s in json.loads((CONTENT / "sections.json").read_text(encoding="utf-8"))}
    arts = sorted((a for a in json.loads((CONTENT / "articles.json").read_text(encoding="utf-8"))
                   if a["section"] == "install"), key=lambda a: (a["order"], a["id"]))
    items = []
    for a in arts:
        md = (CONTENT / lang / f"{a['id']}.md").read_text(encoding="utf-8")
        title = md.splitlines()[0][2:].strip()
        items.append({"id": a["id"], "title": title, "markdown": md})
    sec_title = secs["install"][f"title_{lang}"]
    return ex.to_markdown(sec_title, [{"title": sec_title, "articles": items}])


if __name__ == "__main__":
    (REPO / "docs" / "install.md").write_text(build(), encoding="utf-8")
    print("docs/install.md")
