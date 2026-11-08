"""Compatibility import/CLI for the packaged Icarus runtime."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from icarus.core import runtime as _runtime  # noqa: E402

if __name__ == "__main__":
    _runtime.main()
else:
    sys.modules[__name__] = _runtime
