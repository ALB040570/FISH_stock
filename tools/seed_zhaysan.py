"""Совместимость: прежнее имя скрипта. Загружает только Жайсан — см. tools/seed_samples.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if "--water-body" not in sys.argv:
    sys.argv += ["--water-body", "zhaysan"]
from seed_samples import main  # noqa: E402

main()
