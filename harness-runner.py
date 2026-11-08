"""Compatibility entry point for the packaged evidence runner."""
import runpy


if __name__ == "__main__":
    runpy.run_module("icarus.harness.runner", run_name="__main__")
