"""Compatibility import/CLI for the packaged Icarus duty runner."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from icarus.core import duty_runner as _duty_runner  # noqa: E402

if __name__ == "__main__":
    _duty_runner.main()
else:
    sys.modules[__name__] = _duty_runner
