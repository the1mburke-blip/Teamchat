"""Run the packaged evidence gate or its supervised --route-task entry point."""
import runpy
import sys


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--writeback-issue6":
        from icarus.harness.mailbox import main

        sys.exit(main(sys.argv[2]))
    runpy.run_module("icarus.harness.runner", run_name="__main__")
