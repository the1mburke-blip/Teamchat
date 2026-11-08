"""Turn an issue dispatch into a reviewable draft without executing issue text."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


LABEL = "icarus-dispatch"


def run(*args, env=None, check=True):
    return subprocess.run(
        args, env=env, check=check, stdout=subprocess.PIPE, text=True, encoding="utf-8",
    )


def git(*args):
    return run("git", *args).stdout.strip()


def gh(*args):
    return run("gh", *args).stdout.strip()


def read_dispatch(event_path, repository, number):
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    issue = event["issue"]
    if (number < 1 or type(issue["number"]) is not int or issue["number"] != number
            or event["action"] != "labeled" or event["label"]["name"] != LABEL
            or event["repository"]["full_name"] != repository
            or issue["state"] != "open" or "pull_request" in issue):
        raise ValueError("Event does not match an open issue dispatch in this repository")
    body = issue.get("body")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("Dispatched issue has no Markdown instructions")
    return body, event["repository"]["default_branch"]


def check_issue(repository, number):
    issue = json.loads(gh("issue", "view", str(number), "--repo", repository,
                          "--json", "state,labels"))
    if issue["state"] != "OPEN" or not any(label["name"] == LABEL for label in issue["labels"]):
        raise ValueError("The issue is closed or the dispatch label has been removed")


def prepare_commit(number, instructions, branch, base_sha):
    if git("status", "--porcelain") or git("rev-parse", "HEAD") != base_sha:
        raise ValueError("The worker requires a clean checkout of the event commit")
    path = Path("drafts", "icarus-dispatch", f"issue-{number}.json")
    git("switch", "--create", branch)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as draft:
        json.dump({"issue": number, "instructions": instructions}, draft, ensure_ascii=False, indent=2)
        draft.write("\n")
    git("add", "--", path.as_posix())
    git("-c", "user.name=github-actions[bot]", "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit", "--no-gpg-sign", "-m", f"Record Icarus dispatch for issue #{number}")
    head = git("rev-parse", "HEAD")
    if git("diff", "--name-only", base_sha, head, "--") != path.as_posix():
        raise ValueError("Worker commit contains changes outside the dispatch draft")
    audit = run(sys.executable, "-m", "icarus.harness.runner", "--audit-state-writes",
                env={**os.environ, "ICARUS_AUDIT_BASE": base_sha,
                     "ICARUS_AUDIT_HEAD": head}, check=False)
    print(audit.stdout.strip(), flush=True)
    audit.check_returncode()
    return head


def publish_branch(branch, head):
    ref = f"refs/heads/{branch}"
    remote = run("git", "ls-remote", "--exit-code", "origin", ref, check=False)
    if remote.returncode == 2:
        # An empty expected value prevents a race from replacing an existing branch.
        git("push", f"--force-with-lease={ref}:", "origin", f"{head}:{ref}")
    elif remote.returncode == 0:
        git("fetch", "--no-tags", "origin", ref)
        existing = git("rev-parse", "FETCH_HEAD")
        if (git("rev-parse", f"{existing}^{{tree}}") != git("rev-parse", f"{head}^{{tree}}")
                or git("show", "-s", "--format=%P", existing) != git("show", "-s", "--format=%P", head)):
            raise ValueError("Existing worker branch differs; refusing to overwrite it")
        head = existing
    else:
        raise ValueError("Could not read the worker branch from GitHub")
    if git("ls-remote", "--exit-code", "origin", ref) != f"{head}\t{ref}":
        raise ValueError("Worker branch did not read back at the audited commit")
    return head


def publish_pull_request(repository, number, branch, base, head):
    prs = json.loads(gh("pr", "list", "--repo", repository, "--head", branch,
                        "--base", base, "--state", "all", "--json", "url"))
    if len(prs) > 1:
        raise ValueError("Multiple PRs already exist for the worker branch")
    if prs:
        url = prs[0]["url"]
    else:
        url = gh("pr", "create", "--repo", repository, "--base", base, "--head", branch,
                 "--title", f"Icarus dispatch handoff for issue #{number}", "--body",
                 f"Refs #{number}\n\nThe issue instructions are recorded in a draft for review. "
                 "The worker did not execute the instructions or complete the issue.")
    pr = json.loads(gh("pr", "view", url, "--repo", repository, "--json", "state,headRefOid,url"))
    if pr["state"] != "OPEN" or pr["headRefOid"] != head:
        raise ValueError("Worker PR is not open at the audited commit")
    return pr["url"]


def post_receipt(repository, number, branch, head, url):
    marker = f"<!-- icarus-dispatch-worker:{head} -->"
    endpoint = f"repos/{repository}/issues/{number}/comments"
    receipts = gh("api", "--paginate", endpoint, "--jq",
                  f'.[] | select(.user.login == "github-actions[bot]" and '
                  f'(.body | contains("{marker}"))) | .html_url')
    if receipts:
        return receipts.splitlines()[0]
    body = (f"{marker}\nIcarus dispatch draft: {url}\n\n"
            f"Branch: `{branch}` · Commit: `{head}`\n\n"
            "The completion-integrity check passed for the draft commit. "
            "The issue instructions were recorded, not executed.")
    return gh("issue", "comment", str(number), "--repo", repository, "--body", body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-number", type=int, required=True)
    number = parser.parse_args().issue_number
    try:
        repository = os.environ["GITHUB_REPOSITORY"]
        base_sha = os.environ["GITHUB_SHA"]
        instructions, base = read_dispatch(os.environ["GITHUB_EVENT_PATH"], repository, number)
        check_issue(repository, number)
        branch = f"worker/{number}"
        head = prepare_commit(number, instructions, branch, base_sha)
        head = publish_branch(branch, head)
        url = publish_pull_request(repository, number, branch, base, head)
        print(f"Worker PR: {url}\nIssue receipt: {post_receipt(repository, number, branch, head, url)}")
        return 0
    except (KeyError, TypeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Icarus dispatch stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
