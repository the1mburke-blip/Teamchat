"""Compatibility entry point for the packaged Docker harness launcher."""
from icarus.harness.container import main


if __name__ == "__main__":
    raise SystemExit(main())
