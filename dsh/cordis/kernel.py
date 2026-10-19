# dsh/cordis/kernel.py
import ast
import pathlib
import platform
import re
import shutil
import subprocess
import sys

HARD_DENY = {".git", ".github", "dsh/cordis", "icarus/runtime"}


class VerificationError(RuntimeError):
    """A saved deliverable failed the kernel's static integrity checks."""


_SCRIPT_SUFFIXES = {".py", ".pyw", ".js", ".mjs", ".cjs"}
_STUB_MARKERS = re.compile(
    r"\b(?:TODO|FIXME|TBD|NotImplementedError)\b|"
    r"to\s+register\s*,?\s*point\s+your|plugin\s+loaded|"
    r"your\s+code\s+here|not\s+implemented",
    re.IGNORECASE,
)
_PARENT_ESCAPE = re.compile(r"(?<![\w.])\.\.[/\\]")
_JS_TOKENS = re.compile(
    r"(?P<comment>/\*[\s\S]*?\*/|//[^\r\n]*)|"
    r"(?P<string>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|"
    r"(?P<token>=>|[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|[^\s])"
)


def _python_has_logic(statements):
    """Ignore imports, docstrings, bare stubs, and print-only statements."""
    for statement in statements:
        if isinstance(statement, (ast.Import, ast.ImportFrom, ast.Pass)):
            continue
        if isinstance(statement, ast.Expr):
            value = statement.value
            if isinstance(value, ast.Constant):
                continue
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id == "print"):
                continue
        if isinstance(statement, ast.Return) and (
            statement.value is None
            or isinstance(statement.value, ast.Constant)
            and statement.value.value in (None, Ellipsis)
        ):
            continue
        if isinstance(statement, (ast.If, ast.For, ast.AsyncFor, ast.While)):
            if not _python_has_logic(statement.body + statement.orelse):
                continue
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            if not _python_has_logic(statement.body):
                continue
        if isinstance(statement, (ast.Try, ast.TryStar)):
            bodies = statement.body + statement.orelse + statement.finalbody
            bodies += [part for handler in statement.handlers for part in handler.body]
            if not _python_has_logic(bodies):
                continue
        return True
    return False


def _verify_python(source, path):
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        raise VerificationError(f"Invalid Python syntax: {error}") from error
    nodes = list(ast.walk(tree))
    bindings = {
        item.id for item in nodes
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)
    }
    bindings.update(item.arg for item in nodes if isinstance(item, ast.arg))
    for item in nodes:
        if isinstance(item, (ast.Import, ast.ImportFrom)):
            bindings.update(alias.asname or alias.name.split(".")[0] for alias in item.names)
    for node in nodes:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _PARENT_ESCAPE.search(node.value):
                raise VerificationError("Parent-directory path literal is forbidden")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not _python_has_logic(node.body):
                raise VerificationError(f"Empty or logging-only definition: {node.name}")
        if isinstance(node, ast.Lambda) and isinstance(node.body, ast.Constant):
            if node.body.value in (None, Ellipsis):
                raise VerificationError("Empty lambda definition")
        if isinstance(node, ast.Lambda) and isinstance(node.body, ast.Call):
            if isinstance(node.body.func, ast.Name) and node.body.func.id == "print":
                raise VerificationError("Print-only lambda definition")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            # Catch common omitted standard-library imports without requiring
            # imports in self-contained functions or trying to resolve all names.
            if node.id in {
                "os", "sys", "json", "pathlib", "subprocess", "shutil", "argparse"
            } and node.id not in bindings:
                raise VerificationError(f"Missing import or binding: {node.id}")
    if not _python_has_logic(tree.body):
        raise VerificationError("Python artifact has no active logic or definitions")


def _js_without_logs(tokens):
    result, index = [], 0
    while index < len(tokens):
        if (tokens[index:index + 2] == ["console", "."]
                and tokens[index + 2:index + 3] in (
                    ["log"], ["info"], ["warn"], ["error"], ["debug"], ["trace"]
                ) and tokens[index + 3:index + 4] == ["("]):
            index += 4
            depth = 1
            while index < len(tokens) and depth:
                depth += (tokens[index] == "(") - (tokens[index] == ")")
                index += 1
            continue
        result.append(tokens[index])
        index += 1
    return result


def _js_has_logic(tokens):
    tokens = _js_without_logs(tokens)
    # Imports and directives alone do not implement a script or a plugin.
    filtered, index = [], 0
    while index < len(tokens):
        if tokens[index] == "import" and tokens[index + 1:index + 2] != ["("]:
            while index < len(tokens) and tokens[index] != "<string>":
                index += 1
            index += 1
            continue
        if tokens[index] == "<string>" and (index == 0 or tokens[index - 1] == ";"):
            index += 1
            continue
        filtered.append(tokens[index])
        index += 1
    text = " ".join(filtered)
    text = re.sub(r"\breturn\b\s*(?:(?:undefined|null)\b\s*)?(?=;|$)", "", text)
    return bool(re.search(
        r"\b(?:return|throw)\s+[^;\s]|"
        r"(?<![=<>!])=\s*(?![=;]|$)\S|"
        r"\b(?!(?:if|for|while|switch|catch|with|function)\b)[A-Za-z_$][\w$]*\s*\(|"
        r"\+\s*\+|-\s*-|\bexport\s+default\s+(?:<string>|\d)",
        text,
    ))


def _verify_javascript(source):
    # Lexical checks only: JavaScript behavior still needs project tests.
    tokens = []
    for match in _JS_TOKENS.finditer(source):
        if match.lastgroup == "string":
            try:
                literal = re.sub(
                    r"\\(?:x([0-9a-fA-F]{2})|u([0-9a-fA-F]{4})|u\{([0-9a-fA-F]{1,6})\})",
                    lambda escape: chr(int(next(group for group in escape.groups() if group), 16)),
                    match.group(),
                )
            except ValueError as error:
                raise VerificationError("Invalid JavaScript string escape") from error
            if _PARENT_ESCAPE.search(literal):
                raise VerificationError("Parent-directory path literal is forbidden")
            tokens.append("<string>")
        elif match.lastgroup == "token":
            tokens.append(match.group())
    for index, token in enumerate(tokens):
        if token == "=>" and tokens[index + 1:index + 2] != ["{"]:
            end = index + 1
            while end < len(tokens) and tokens[end] not in (";", "}"):
                end += 1
            expression = tokens[index + 1:end]
            remaining = [part for part in _js_without_logs(expression) if part not in ("(", ")")]
            if not remaining or remaining in (["undefined"], ["null"]):
                raise VerificationError("Empty or console-only JavaScript arrow export")
        # Covers function exports, arrow functions, and ordinary method bodies.
        if token != "{" or index == 0 or tokens[index - 1] not in (")", "=>"):
            continue
        end, depth = index + 1, 1
        while end < len(tokens) and depth:
            depth += (tokens[end] == "{") - (tokens[end] == "}")
            end += 1
        if depth:
            raise VerificationError("Unclosed JavaScript body")
        if not _js_has_logic(tokens[index + 1:end - 1]):
            raise VerificationError("Empty or console-only JavaScript body")
    for index, token in enumerate(tokens):
        if token != "class":
            continue
        start = index + 1
        while start < len(tokens) and tokens[start] != "{":
            start += 1
        end, depth = start + 1, 1
        while end < len(tokens) and depth:
            depth += (tokens[end] == "{") - (tokens[end] == "}")
            end += 1
        if depth or not _js_has_logic(tokens[start + 1:end - 1]):
            raise VerificationError("Empty or incomplete JavaScript class")
    text = " ".join(_js_without_logs(tokens)).strip(" ;")
    if not _js_has_logic(tokens) or re.fullmatch(
        r"(?:module \. exports =|exports \. \w+ =|export default|export)"
        r"\s*(?:\{\s*\}|undefined|null)", text
    ):
        raise VerificationError("JavaScript artifact has no active logic or exports")


def verify_deliverable_integrity(file_path: str) -> None:
    """Inspect a physical artifact; never execute generated code here.

    Script markers and parent-directory literals are rejected conservatively,
    including in comments/documentation. Static checks do not prove runtime
    success, registration, or safety of dynamically constructed paths.
    """
    path = pathlib.Path(file_path)
    if not path.is_file():
        raise VerificationError(f"Deliverable is missing or not a file: {path}")
    if path.suffix.lower() not in _SCRIPT_SUFFIXES:
        return
    try:
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise VerificationError(f"Cannot read script artifact: {error}") from error
    marker = _STUB_MARKERS.search(source)
    if marker:
        raise VerificationError(f"Unresolved placeholder: {marker.group()}")
    if _PARENT_ESCAPE.search(source):
        raise VerificationError("Parent-directory path literal is forbidden")
    if path.suffix.lower() in {".py", ".pyw"}:
        _verify_python(source, path)
    else:
        _verify_javascript(source)


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

        if backup_file.exists():
            raise VerificationError(f"Refusing to overwrite existing backup: {backup_file}")
        if had_original:
            with backup_file.open("xb") as backup:
                backup.write(p.read_bytes())

        # Select test runner or fallback to native syntax check
        if shutil.which("pytest"):
            test_cmd = ["pytest"]
            test_desc = "pytest test suite"
        else:
            test_cmd = [sys.executable, "-m", "py_compile", str(p)]
            test_desc = "py_compile syntax check (pytest not installed)"

        mode_desc = f"deliverable integrity check before {test_desc}"
        try:
            p.write_text(patch_content, encoding="utf-8")
            verify_deliverable_integrity(str(p))
            mode_desc = test_desc
            res = subprocess.run(
                test_cmd, cwd=self.root, capture_output=True, text=True
            )
            passed = res.returncode == 0
            err_msg = f"{res.stdout}\n{res.stderr}"
            if passed:
                mode_desc = f"post-test deliverable integrity check after {test_desc}"
                verify_deliverable_integrity(str(p))
                mode_desc = f"{test_desc} and deliverable integrity checks"
        except Exception as ex:
            passed = False
            err_msg = f"{type(ex).__name__}: {ex}"

        if not passed:
            if had_original and backup_file.is_file():
                p.write_bytes(backup_file.read_bytes())
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
