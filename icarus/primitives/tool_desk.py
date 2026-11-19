"""External Composio tool desk for explicitly authorized job actions.

Only BUFFER_CREATE_POST_DRAFT is exposed to model plans. The worker executes
it in the daemon process, outside the no-network command container. It is
never allowed to publish or send. Every API request is logged locally and,
when supplied, durably to the GitLedger hash-chained run log.

Job verify_spec example (values are supplied by the task author, not model):
  "allowed_tools": {
    "BUFFER_CREATE_POST_DRAFT": {
      "connected_account_id": "buffer_<account>",
      "organization_id": "<organization>",
      "allowed_channel_ids": ["<channel>"]
    }
  }

Model plan example:
  "tool_calls": [{"tool_slug":"BUFFER_CREATE_POST_DRAFT",
                   "arguments":{"channel_id":"<channel>","text":"..."}}]

The verifier independently lists Buffer drafts after execution and requires
one exact text/channel match before the job can pass. A preflight read avoids
creating duplicates on a retry after an uncertain network result.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable

API_BASE = "https://backend.composio.dev/api/v3.1/tools/execute"
ACTION = "BUFFER_CREATE_POST_DRAFT"
READBACK = "BUFFER_LIST_POSTS"
MAX_TOOL_CALLS = 2


class ToolDeskError(Exception):
    """A denied, failed, or unverifiable external tool operation."""


def _sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def model_tool_contract(spec: dict) -> list[dict]:
    """Expose only supported action names/arguments; never account or org IDs."""
    allowed = spec.get("allowed_tools", {}) if isinstance(spec, dict) else {}
    if not isinstance(allowed, dict):
        return []
    out = []
    cfg = allowed.get(ACTION)
    if isinstance(cfg, dict):
        channels = cfg.get("allowed_channel_ids", [])
        out.append({"tool_slug": ACTION,
                    "arguments": {"required": ["channel_id", "text"],
                                  "allowed": ["channel_id", "text"],
                                  "allowed_channel_ids": list(channels) if isinstance(channels, list) else []}})
    return out


class ToolDesk:
    def __init__(self, api_key: str | None = None, timeout: int = 30,
                 opener: Callable | None = None, event_logger: Callable | None = None):
        self.api_key = (api_key if api_key is not None else os.environ.get("COMPOSIO_API_KEY", "")).strip()
        self.timeout = timeout
        self.opener = opener or urllib.request.urlopen
        self.event_logger = event_logger
        self.receipts: list[dict] = []

    def _log(self, job_dir: str | Path, event: dict) -> None:
        path = Path(job_dir) / "tool_calls.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")
        if self.event_logger:
            try:
                self.event_logger(dict(event))
            except Exception as e:
                raise ToolDeskError(f"tool event could not be persisted: {type(e).__name__}") from e

    def _request(self, slug: str, account_id: str, arguments: dict,
                 job_dir: str | Path, kind: str) -> dict:
        if slug not in (ACTION, READBACK):
            raise ToolDeskError(f"tool not in internal allowlist: {slug}")
        call_id = uuid.uuid4().hex
        base = {"call_id": call_id, "tool_slug": slug, "kind": kind,
                "arguments_sha256": _sha(arguments), "account_sha256": _sha(account_id)}
        self._log(job_dir, {**base, "status": "started"})
        if not self.api_key:
            self._log(job_dir, {**base, "status": "failed", "error_code": "missing_api_key"})
            raise ToolDeskError("COMPOSIO_API_KEY is not configured")
        body = {"connected_account_id": account_id, "arguments": arguments}
        req = urllib.request.Request(
            f"{API_BASE}/{slug}", data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-api-key": self.api_key}, method="POST")
        try:
            with self.opener(req, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                raw = response.read()
        except urllib.error.HTTPError as e:
            self._log(job_dir, {**base, "status": "failed", "http_status": e.code,
                                "error_code": "http_error"})
            raise ToolDeskError(f"{slug} failed with HTTP {e.code}") from e
        except Exception as e:
            self._log(job_dir, {**base, "status": "failed", "error_code": type(e).__name__})
            raise ToolDeskError(f"{slug} request failed: {type(e).__name__}") from e
        if not 200 <= status < 300:
            self._log(job_dir, {**base, "status": "failed", "http_status": status,
                                "error_code": "http_status"})
            raise ToolDeskError(f"{slug} failed with HTTP {status}")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._log(job_dir, {**base, "status": "failed", "http_status": status,
                                "error_code": "invalid_json"})
            raise ToolDeskError(f"{slug} returned invalid JSON") from e
        if not isinstance(envelope, dict) or envelope.get("successful") is False or envelope.get("error"):
            self._log(job_dir, {**base, "status": "failed", "http_status": status,
                                "composio_log_id": envelope.get("log_id") if isinstance(envelope, dict) else None,
                                "error_code": "composio_error"})
            raise ToolDeskError(f"{slug} returned an unsuccessful Composio response")
        self._log(job_dir, {**base, "status": "completed", "http_status": status,
                            "composio_log_id": envelope.get("log_id"),
                            "external_id": self._external_id(envelope)})
        return envelope

    @staticmethod
    def _data(envelope: dict) -> dict:
        data = envelope.get("data", {})
        return data if isinstance(data, dict) else {}

    @classmethod
    def _external_id(cls, envelope: dict) -> str | None:
        data = cls._data(envelope)
        for obj in (data, data.get("post"), data.get("item")):
            if isinstance(obj, dict):
                for key in ("id", "post_id", "postId"):
                    if obj.get(key) is not None:
                        return str(obj[key])
        return None

    @staticmethod
    def _post_id(post: dict) -> str | None:
        for key in ("id", "post_id", "postId"):
            if post.get(key) is not None:
                return str(post[key])
        return None

    @staticmethod
    def _items(envelope: dict) -> list[dict]:
        data = envelope.get("data", {})
        if isinstance(data, dict):
            items = data.get("items", data.get("posts", []))
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
        return []

    @staticmethod
    def _channel_id(post: dict) -> str | None:
        value = post.get("channel_id", post.get("channelId"))
        if isinstance(value, dict):
            value = value.get("id")
        if value is None and isinstance(post.get("channel"), dict):
            value = post["channel"].get("id")
        return str(value) if value is not None else None

    def _list_posts(self, cfg: dict, channel_id: str, job_dir: str | Path, kind: str) -> list[dict]:
        account = cfg["connected_account_id"]
        args = {"organization_id": cfg["organization_id"], "channel_ids": [channel_id],
                "statuses": ["draft"], "page_size": 50, "sort_field": "createdAt",
                "sort_direction": "desc"}
        items, cursor = [], None
        for _ in range(5):
            page_args = dict(args)
            if cursor:
                page_args["cursor"] = cursor
            envelope = self._request(READBACK, account, page_args, job_dir, kind)
            items.extend(self._items(envelope))
            cursor = self._data(envelope).get("next_cursor")
            if not cursor:
                break
        return items

    def _matches(self, posts: list[dict], args: dict) -> list[dict]:
        matches = []
        for post in posts:
            text = post.get("text", post.get("content"))
            if text != args["text"]:
                continue
            channel = self._channel_id(post)
            if channel and channel != args["channel_id"]:
                continue
            status = str(post.get("status", post.get("state", "draft"))).lower()
            if status != "draft":
                continue
            matches.append(post)
        return matches

    def _config(self, slug: str, spec: dict, args: dict) -> dict:
        if slug != ACTION:
            raise ToolDeskError(f"tool not in job allowlist: {slug}")
        allowed = spec.get("allowed_tools", {})
        cfg = allowed.get(slug) if isinstance(allowed, dict) else None
        if not isinstance(cfg, dict):
            raise ToolDeskError(f"job did not authorize {slug}")
        if set(args) - {"channel_id", "text"}:
            raise ToolDeskError("tool arguments contain unsupported fields")
        if not isinstance(args.get("text"), str) or not args["text"].strip():
            raise ToolDeskError("Buffer draft text is required")
        channels = cfg.get("allowed_channel_ids")
        if not isinstance(channels, list) or args.get("channel_id") not in channels:
            raise ToolDeskError("channel_id is not authorized by this job")
        if not cfg.get("connected_account_id") or not cfg.get("organization_id"):
            raise ToolDeskError("Buffer account and organization IDs must be fixed in job checks")
        return cfg

    def execute_calls(self, planned: list, spec: dict, job_dir: str | Path) -> list[dict]:
        self.receipts = []
        if not isinstance(planned, list) or len(planned) > MAX_TOOL_CALLS:
            raise ToolDeskError(f"tool_calls must be a list of at most {MAX_TOOL_CALLS}")
        for index, call in enumerate(planned):
            if not isinstance(call, dict) or set(call) - {"tool_slug", "arguments"}:
                raise ToolDeskError("each tool call must contain only tool_slug and arguments")
            slug, args = call.get("tool_slug"), call.get("arguments")
            if not isinstance(args, dict):
                raise ToolDeskError("tool call arguments must be an object")
            cfg = self._config(slug, spec, args)
            posts = self._list_posts(cfg, args["channel_id"], job_dir, "preflight")
            matches = self._matches(posts, args)
            if len(matches) > 1:
                raise ToolDeskError("multiple identical Buffer drafts already exist; refusing to duplicate")
            if matches:
                status, external_id = "already_exists", self._post_id(matches[0])
            else:
                action_args = {"channel_id": args["channel_id"], "text": args["text"],
                               "ai_assisted": True, "needs_approval": bool(cfg.get("needs_approval", False))}
                result = self._request(ACTION, cfg["connected_account_id"], action_args, job_dir, "action")
                status, external_id = "created", self._external_id(result)
            self.receipts.append({"index": index, "tool_slug": slug, "status": status,
                                  "external_id": external_id, "arguments_sha256": _sha(args)})
        return list(self.receipts)

    def verify_calls(self, planned: list, receipts: list, spec: dict,
                     job_dir: str | Path) -> dict:
        reasons, checked = [], []
        if not isinstance(receipts, list) or len(planned) != len(receipts):
            return {"pass": False, "calls": [], "reasons": ["tool receipt count does not match plan"]}
        for index, (call, receipt) in enumerate(zip(planned, receipts)):
            slug, args = call.get("tool_slug"), call.get("arguments", {})
            try:
                cfg = self._config(slug, spec, args)
                if receipt.get("tool_slug") != slug or receipt.get("arguments_sha256") != _sha(args):
                    raise ToolDeskError("tool receipt does not match the planned call")
                posts = self._list_posts(cfg, args["channel_id"], job_dir, "readback")
                matches = self._matches(posts, args)
                external_id = receipt.get("external_id")
                if external_id:
                    matches = [p for p in matches if self._post_id(p) == str(external_id)]
                if len(matches) != 1:
                    raise ToolDeskError("Buffer readback did not find exactly one matching draft")
                post_id = self._post_id(matches[0])
                checked.append({"index": index, "tool_slug": slug, "verified": True,
                                "external_id": post_id, "status": "draft"})
            except ToolDeskError as e:
                reasons.append(f"tool call {index}: {e}")
                checked.append({"index": index, "tool_slug": slug, "verified": False,
                                "reason": str(e)})
        return {"pass": not reasons, "calls": checked, "reasons": reasons}
