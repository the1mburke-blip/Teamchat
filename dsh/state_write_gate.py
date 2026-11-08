"""Read-only admission audit for completion claims in Git-tracked state.

This module does not intercept GitHub writes or issue closures. Required remote
checks and removal of worker admin/workflow/issue-write permissions are separate
deployment prerequisites. GitHub artifact digests provide integrity, not an
offline signature or protection from an administrator changing the verifier.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile


REPOSITORY = "the1mburke-blip/Teamchat"
REPOSITORY_ID = 1383566901
WORKFLOW_ID = 408772344
WORKFLOW_PATH = ".github/workflows/icarus-harness-gate.yml"
RECEIPTS = ".icarus/receipts/"
LIMIT = 4 * 1024 * 1024
TRUSTED_FILES = (WORKFLOW_PATH, "harness-runner.py", "harness_runner.py",
                 "icarus/harness/runner.py", "icarus/harness/container.py",
                 "Dockerfile", "dsh/state_write_gate.py", "dsh/execution_integrity.py",
                 "docker/verify-and-test.py")
CLAIM = re.compile(r"\[STATUS\]\s*(?:PASS|COMPLETED|DONE)\b|\bCOMPLETED\b|"
                   r"[\"']?(?:status|state|verdict)[\"']?\s*[:=]\s*[\"']?(?:PASS|DONE)\b", re.I)
SHA = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


class Rejected(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Rejected(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def parse(raw):
    def constant(value):
        raise Rejected("Non-finite JSON value")
    return json.loads(raw, object_pairs_hook=unique, parse_constant=constant)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def valid_path(path):
    return (isinstance(path, str) and bool(path) and "\\" not in path
            and "\0" not in path and ":" not in path
            and not PurePosixPath(path).is_absolute()
            and all(part not in ("", ".", "..") for part in path.split("/")))


def protected(path):
    p = PurePosixPath(path)
    if path.startswith((RECEIPTS, ".github/", "docs/", "tests/")):
        return False
    return (p.name.casefold() == "chat_log.md" or
            p.suffix.casefold() in {".md", ".json", ".jsonl", ".csv", ".tsv"}
            and re.search(r"state|status|ledger|^goal\.", p.name, re.I) is not None)


class Git:
    def __init__(self, root="."):
        self.root = root

    def run(self, *args):
        result = subprocess.run(["git", *args], cwd=self.root, capture_output=True,
                                timeout=30, check=False)
        require(result.returncode == 0, "Git read failed: " + args[0])
        return result.stdout

    def blob(self, ref, path):
        require(COMMIT.fullmatch(ref) and valid_path(path), "Invalid Git object selector")
        mode = self.run("ls-tree", ref, "--", path).split(b" ", 1)[0]
        require(mode in (b"100644", b"100755"), "Missing or non-regular file: " + path)
        return self.run("show", ref + ":" + path)

    def changed(self, base, head):
        return [name.decode("utf-8") for name in
                self.run("diff", "--name-only", "-z", base, head, "--").split(b"\0") if name]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        return None


class GitHub:
    def __init__(self, token):
        require(bool(token), "GitHub read credential missing")
        self.token = token

    def request(self, path):
        require(path.startswith("/repos/" + REPOSITORY + "/"), "Invalid API endpoint")
        return urllib.request.Request("https://api.github.com" + path, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json", "User-Agent": "icarus-state-write-gate",
            "X-GitHub-Api-Version": "2022-11-28"})

    @staticmethod
    def read(handle):
        data = handle.read(LIMIT + 1)
        require(len(data) <= LIMIT, "API/artifact exceeds size limit")
        return data

    def get(self, suffix):
        with urllib.request.urlopen(self.request("/repos/" + REPOSITORY + suffix), timeout=20) as handle:
            return parse(self.read(handle))

    def archive(self, artifact_id):
        request = self.request(f"/repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip")
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as handle:
                return self.read(handle)
        except urllib.error.HTTPError as error:
            require(error.code in (301, 302, 303, 307, 308), "Artifact download rejected")
            location = error.headers.get("Location", "")
        target = urllib.parse.urlsplit(location)
        require(target.scheme == "https" and target.hostname and not target.username
                and not target.password, "Invalid artifact redirect")
        # Never forward the GitHub bearer token to blob storage.
        with urllib.request.urlopen(location, timeout=20) as handle:
            return self.read(handle)


def receipt_schema(receipt):
    keys = {"version", "task_id", "harness_run_id", "run_attempt", "artifact_id",
            "artifact_sha256", "source_commit", "artifacts"}
    require(isinstance(receipt, dict) and set(receipt) == keys, "Invalid receipt fields")
    require(type(receipt["version"]) is int and receipt["version"] == 1, "Invalid receipt version")
    require(isinstance(receipt["task_id"], str) and
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", receipt["task_id"]), "Invalid task ID")
    for name in ("harness_run_id", "run_attempt", "artifact_id"):
        require(type(receipt[name]) is int and receipt[name] > 0, "Invalid " + name)
    require(isinstance(receipt["source_commit"], str) and
            COMMIT.fullmatch(receipt["source_commit"]), "Invalid source commit")
    require(isinstance(receipt["artifact_sha256"], str) and
            SHA.fullmatch(receipt["artifact_sha256"]), "Invalid artifact digest")
    artifacts = receipt["artifacts"]
    require(isinstance(artifacts, dict) and bool(artifacts), "Receipt artifacts missing")
    for path, expected in artifacts.items():
        require(valid_path(path) and protected(path) and isinstance(expected, str)
                and SHA.fullmatch(expected), "Invalid receipt artifact")


def manifest_from_archive(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        require(len(names) == len(set(names)), "Duplicate archive member")
        require(set(names) == {"RUN_LOG.jsonl", "COMPLETION_MANIFEST.json"}, "Unexpected artifact members")
        require(all(member.file_size <= LIMIT and not member.flag_bits & 1
                    for member in members), "Oversized or encrypted artifact")
        with archive.open("COMPLETION_MANIFEST.json") as stream:
            content = stream.read(LIMIT + 1)
        require(len(content) <= LIMIT, "Manifest exceeds size limit")
        manifest = parse(content)
        require(isinstance(manifest, dict), "Invalid manifest")
        return manifest


def verify_receipt(receipt, git, api, base, head):
    receipt_schema(receipt)
    source = receipt["source_commit"]
    ancestor = git.run("merge-base", source, head).decode().strip()
    require(ancestor == source, "Proof source is not an ancestor of this candidate")
    require(all(path.startswith(RECEIPTS) and path.endswith(".json")
                for path in git.changed(source, head)), "Code/state changed after the proof run")
    run_id, attempt = receipt["harness_run_id"], receipt["run_attempt"]
    run = api.get(f"/actions/runs/{run_id}")
    require(run.get("id") == run_id and run.get("run_attempt") == attempt
            and run.get("status") == "completed"
            and run.get("conclusion") in {"success", "failure"}
            and run.get("head_sha") == source
            and run.get("workflow_id") == WORKFLOW_ID
            and run.get("path") == WORKFLOW_PATH
            and run.get("repository", {}).get("id") == REPOSITORY_ID
            and run.get("head_repository", {}).get("id") == REPOSITORY_ID
            and run.get("event") in {"pull_request", "push"}, "Run identity/result mismatch")
    for path in TRUSTED_FILES:
        content = api.get("/contents/" + path + "?ref=" + source)
        require(content.get("encoding") == "base64", "Unexpected source encoding")
        observed = base64.b64decode(content["content"], validate=False)
        require(observed == git.blob(base, path), "Untrusted proof producer: " + path)
    jobs = api.get(f"/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    require(jobs.get("total_count", 101) <= 100, "Job listing incomplete")
    harness = [job for job in jobs.get("jobs", []) if job.get("name") == "harness"]
    require(len(harness) == 1 and harness[0].get("status") == "completed"
            and harness[0].get("conclusion") == "success", "Harness did not succeed")
    require(all(job.get("name") == "completion-integrity" or
                job.get("conclusion") == "success" for job in jobs["jobs"]), "Other producer job failed")
    # The admission job can fail for a missing receipt while the independent
    # harness producer succeeds. A later receipt-only commit resolves that cycle.
    artifacts = api.get(f"/actions/runs/{run_id}/artifacts?per_page=100")
    require(artifacts.get("total_count", 101) <= 100, "Artifact listing incomplete")
    matches = [item for item in artifacts.get("artifacts", [])
               if item.get("name") == f"harness-run-log-{run_id}-{attempt}"]
    require(len(matches) == 1, "Proof artifact missing or ambiguous")
    artifact = matches[0]
    require(artifact.get("id") == receipt["artifact_id"] and not artifact.get("expired")
            and artifact.get("digest") == "sha256:" + receipt["artifact_sha256"], "Artifact identity/digest mismatch")
    raw = api.archive(receipt["artifact_id"])
    require(digest(raw) == receipt["artifact_sha256"], "Downloaded artifact hash mismatch")
    manifest = manifest_from_archive(raw)
    require(manifest.get("evaluator") == "CHAIR_JUDGE" and manifest.get("verdict") == "PASS"
            and manifest.get("readback_status") == "VERIFIED"
            and type(manifest.get("exit_code")) is int and manifest["exit_code"] == 0
            and manifest.get("repository_id") == REPOSITORY_ID
            and manifest.get("source_commit") == source
            and manifest.get("harness_run_id") == run_id
            and manifest.get("run_attempt") == attempt
            and manifest.get("task_id") == receipt["task_id"], "Manifest binding mismatch")
    require(isinstance(manifest.get("artifacts"), dict), "Manifest hashes missing")
    for path, expected in receipt["artifacts"].items():
        require(manifest["artifacts"].get(path) == expected
                and digest(git.blob(head, path)) == expected, "Modified state hash mismatch: " + path)
    return set(receipt["artifacts"])


def audit(git, base, head, api=None):
    require(COMMIT.fullmatch(base) and COMMIT.fullmatch(head), "Invalid audit revisions")
    base = git.run("merge-base", base, head).decode().strip()
    changed = git.changed(base, head)
    needed = set()
    for path in changed:
        if not protected(path):
            continue
        current = git.blob(head, path)
        if PurePosixPath(path).name.casefold() == "chat_log.md":
            previous = git.blob(base, path)
            require(current.startswith(previous), "CHAT_LOG.md is append-only")
            if CLAIM.search(current[len(previous):].decode("utf-8")):
                needed.add(path)
        else:
            needed.add(path)
    if not needed:
        return {"audit": "PASS", "completion_claims": 0}
    receipts = [path for path in changed if path.startswith(RECEIPTS) and path.endswith(".json")]
    require(bool(receipts), "No completion receipt accompanies the state write")
    require(api is not None, "Remote CI proof verifier unavailable")
    covered = set()
    for path in receipts:
        receipt = parse(git.blob(head, path))
        covered |= verify_receipt(receipt, git, api, base, head)
    require(needed <= covered, "Completion receipt does not cover every state write")
    return {"audit": "PASS", "completion_claims": len(needed)}


def write_manifest(output):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Manifest production requires GitHub Actions")
    require(os.environ.get("ICARUS_HARNESS_OUTCOME") == "success", "Harness step did not succeed")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "Wrong repository")
    git = Git()
    source = os.environ["ICARUS_SOURCE_SHA"]
    require(COMMIT.fullmatch(source), "Invalid source commit")
    artifacts = {}
    for raw in git.run("ls-files", "-z").split(b"\0"):
        if not raw:
            continue
        name = raw.decode("utf-8")
        if protected(name):
            path = Path(name)
            require(path.is_file() and not path.is_symlink(), "Non-regular state artifact")
            artifacts[name] = digest(path.read_bytes())
    manifest = {"evaluator": "CHAIR_JUDGE", "verdict": "PASS", "readback_status": "VERIFIED",
                "exit_code": 0, "repository_id": REPOSITORY_ID,
                "task_id": os.environ["ICARUS_TASK_ID"], "source_commit": source,
                "harness_run_id": int(os.environ["GITHUB_RUN_ID"]),
                "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]), "artifacts": artifacts}
    Path(output).write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")


def audit_cli():
    git = Git()
    try:
        base = git.run("rev-parse", os.environ.get("ICARUS_AUDIT_BASE", "origin/main") + "^{commit}").decode().strip()
        head = git.run("rev-parse", os.environ.get("ICARUS_AUDIT_HEAD", "HEAD") + "^{commit}").decode().strip()
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        result = audit(git, base, head, GitHub(token) if token else None)
        print(json.dumps(result))
        return 0
    except (Rejected, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print("FRAUDULENT_OR_UNVERIFIED_COMPLETION_CLAIM: " + str(error))
        return 1


def receipt_from_run(run_id, output):
    """Generate a receipt from authenticated evidence, never a local assertion."""
    require(type(run_id) is int and run_id > 0, "Invalid run ID")
    require(valid_path(output) and output.startswith(RECEIPTS)
            and output.endswith(".json"), "Receipt must be under " + RECEIPTS)
    api = GitHub(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    run = api.get(f"/actions/runs/{run_id}")
    attempt = run["run_attempt"]
    listing = api.get(f"/actions/runs/{run_id}/artifacts?per_page=100")
    require(listing.get("total_count", 101) <= 100, "Artifact listing incomplete")
    matches = [item for item in listing.get("artifacts", [])
               if item.get("name") == f"harness-run-log-{run_id}-{attempt}"]
    require(len(matches) == 1, "Proof artifact missing or ambiguous")
    artifact = matches[0]
    raw = api.archive(artifact["id"])
    manifest = manifest_from_archive(raw)
    receipt = {"version": 1, "task_id": manifest["task_id"], "harness_run_id": run_id,
               "run_attempt": attempt, "artifact_id": artifact["id"],
               "artifact_sha256": digest(raw), "source_commit": run["head_sha"],
               "artifacts": manifest["artifacts"]}
    git = Git()
    base = git.run("rev-parse", "origin/main^{commit}").decode().strip()
    head = git.run("rev-parse", "HEAD^{commit}").decode().strip()
    verify_receipt(receipt, git, api, base, head)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, sort_keys=True) + "\n")
