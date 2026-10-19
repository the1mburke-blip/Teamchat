# dsh/cordis/kernel.py
import pathlib
import platform
import subprocess
import sys
import shutil

HARD_DENY = {".git", ".github", "dsh/cordis", "icarus/runtime"}


def notify_human(title: str, message: str):
    """Triggers a native desktop OS notification pop-up on pass or fail."""
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.run(["notify-send", title, message], check=False)
        elif system == "Darwin":  # macOS
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{message}" with title "{title}"',
                ],
                check=False,
            )
        elif system == "Windows":
            ps_cmd = f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show("{message}", "{title}")'
            subprocess.run(["powershell", "-Command", ps_cmd], check=False)
    except Exception as e:
        print(f"Notification error: {e}", file=sys.stderr)


class CordisKernel:

    def __init__(self, workspace_root: str = "."):
        self.root = pathlib.Path(workspace_root).resolve()

    def validate_path(self, target_file: str) -> None:
        p = (self.root / target_file).resolve()

        # 1. Block any path attempting to escape the workspace root
        try:
            rel = p.relative_to(self.root).as_posix()
        except ValueError:
            notify_human(
                "Icarus Kernel Halt",
                f"BLOCKED: Out-of-workspace path attempt on {target_file}",
            )
            print(
                f"[CORDIS HALT] Path outside workspace: {target_file}",
                file=sys.stderr,
            )
            sys.exit(1)

        rel_lower = rel.lower()

        # 2. Case-insensitive matching for all protected paths
        for deny in HARD_DENY:
            d_lower = deny.lower()
            if (
                rel_lower == d_lower
                or rel_lower.startswith(d_lower + "/")
                or f"/{d_lower}/" in f"/{rel_lower}/"
            ):
                notify_human(
                    "Icarus Kernel Halt",
                    f"BLOCKED: Protected path attempt on {target_file}",
                )
                print(
                    f"[CORDIS HALT] Protected path violation: {target_file}",
                    file=sys.stderr,
                )
                sys.exit(1)

    def apply_and_verify(self, target_file: str, patch_content: str) -> None:
        self.validate_path(target_file)
        p = (self.root / target_file).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        backup_file = p.with_suffix(p.suffix + ".bak")
        had_original = p.is_file()

        if had_original:
            backup_file.write_text(
                p.read_text(encoding="utf-8"), encoding="utf-8"
            )

        p.write_text(patch_content, encoding="utf-8")

        # Select test runner or fallback to native syntax check
        if shutil.which("pytest"):
            test_cmd = ["pytest"]
            mode_desc = "pytest test suite"
        else:
            test_cmd = [sys.executable, "-m", "py_compile", str(p)]
            mode_desc = "py_compile syntax check (pytest not installed)"

        try:
            res = subprocess.run(
                test_cmd, cwd=self.root, capture_output=True, text=True
            )
            passed = res.returncode == 0
            err_msg = f"{res.stdout}\n{res.stderr}"
        except Exception as ex:
            passed = False
            err_msg = str(ex)

        if not passed:
            if had_original and backup_file.is_file():
                p.write_text(
                    backup_file.read_text(encoding="utf-8"), encoding="utf-8"
                )
                backup_file.unlink(missing_ok=True)
            elif not had_original and p.is_file():
                p.unlink(missing_ok=True)

            notify_human(
                "Icarus Kernel Rollback",
                f"FAILED: Verification failed ({mode_desc}) on {target_file}. Changes wiped.",
            )
            print(
                f"[CORDIS ROLLBACK] Verification failed for {target_file} via {mode_desc}.\n{err_msg}",
                file=sys.stderr,
            )
            sys.exit(1)

        if backup_file.is_file():
            backup_file.unlink(missing_ok=True)

        notify_human(
            "Icarus Kernel Success",
            f"PASSED: Changes verified ({mode_desc}) and applied to {target_file}.",
        )
        print(f"[CORDIS SUCCESS] Changes verified on {target_file} via {mode_desc}.")
