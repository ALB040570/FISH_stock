"""Статья справки «Слайды мониторинга: как читать» совпадает с шаблоном мониторинга и пояснениями (tools/gen_slides_help.py)."""
import importlib.util

from conftest import REPO


def test_slides_help_in_sync():
    spec = importlib.util.spec_from_file_location("gen_slides_help", REPO / "tools" / "gen_slides_help.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    for lang in ("ru", "kk"):
        assert gen.path(lang).read_text(encoding="utf-8") == gen.build(lang), \
            f"статья monitoring-slides ({lang}) отстала — выполните python tools/gen_slides_help.py"
