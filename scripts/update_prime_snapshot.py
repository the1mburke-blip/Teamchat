"""Compatibility import/CLI for the packaged Prime snapshot updater."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from icarus.core import snapshot as _snapshot  # noqa: E402

if __name__ == "__main__":
    _snapshot.main()
else:
    sys.modules[__name__] = _snapshot
