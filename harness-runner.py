"""Run the packaged evidence gate or its supervised --route-task entry point."""
import runpy


if __name__ == "__main__":
    runpy.run_module("icarus.harness.runner", run_name="__main__")
