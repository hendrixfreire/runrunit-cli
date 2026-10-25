#!/usr/bin/env python3
"""Safe stdlib client for documented Runrun.it API task operations."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE_URL = "https://runrun.it/api/v1.0"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
ACTIONS = {
    "play", "pause", "change_board", "change_project", "change_type",
    "deliver", "reopen", "reposition", "reestimate", "share", "unshare",
    "complete_workflow_step", "undo_workflow_step", "mark_as_urgent",
    "unmark_as_urgent", "create_assignments", "move_to_top",
    "move_to_next_stage", "move",
}
VISIBLE_HEADERS = {
    "content-type", "link", "x-item-range", "x-item-without-view-permission",
    "ratelimit-limit", "ratelimit-remaining", "ratelimit-reset", "etag",
}


def credentials() -> tuple[str, str]:
    app_key = os.environ.get("RUNRUNIT_APP_KEY")
    user_token = os.environ.get("RUNRUNIT_USER_TOKEN")
    if not app_key or not user_token:
        raise SystemExit(
            "Set RUNRUNIT_APP_KEY and RUNRUNIT_USER_TOKEN in the secret environment."
        )
    return app_key, user_token


def safe_id(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise SystemExit(f"Unsafe identifier: {value!r}")
    return value


def normalize_path(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        raise SystemExit("Path must start with one slash, for example /tasks/123.")
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc:
        raise SystemExit("Only relative API paths are accepted.")
    if ".." in parsed.path.split("/"):
        raise SystemExit("Parent path segments are not accepted.")
    return path


def parse_pairs(values: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Expected key=value, got {value!r}")
        key, item = value.split("=", 1)
        if not key:
            raise SystemExit("Query key cannot be empty.")
        pairs.append((key, item))
    return pairs


def add_query(path: str, pairs: list[tuple[str, str]]) -> str:
    parsed = urlparse(path)
    merged = parse_qsl(parsed.query, keep_blank_values=True) + pairs
    query = urlencode(merged)
    return parsed.path + ("?" + query if query else "")


def parse_data(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in --data: {exc}") from exc


def visible_headers(headers: Any) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() in VISIBLE_HEADERS}


def decode_body(raw: bytes, content_type: str | None) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    if content_type and "json" in content_type.lower():
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return text


class RedirectBlockedError(Exception):
    """An HTTP redirect was refused so credentials cannot reach another origin."""

    def __init__(self, code: int, target: str) -> None:
        super().__init__(f"HTTP {code} redirect to {target} blocked")
        self.code = code
        self.target = target


def _reported_origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        return "(relative)"
    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError:
        port = ""
    return f"{parsed.scheme}://{parsed.hostname or ''}{port}"


class NoRedirectHandler(HTTPRedirectHandler):
    """Refuse every redirect instead of re-sending App-Key/User-Token.

    urllib would otherwise follow 3xx responses, forward the authentication
    headers to whatever origin (or plain HTTP URL) the Location names, and
    turn a redirected POST into a GET. Pagination has its own allow-list in
    next_link; transport-level redirects are never trusted.
    """

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        close = getattr(fp, "close", None)
        if callable(close):
            close()
        raise RedirectBlockedError(code, _reported_origin(newurl))


def urlopen(request: Request, timeout: int = 30) -> Any:
    """Redirect-safe replacement for the stdlib helper, kept as a module seam.

    A 3xx must never trigger a second request carrying App-Key/User-Token.
    """
    opener = build_opener(NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def call(method: str, path: str, data: Any = None, if_none_match: str | None = None, allow_not_found: bool = False) -> dict[str, Any]:
    app_key, user_token = credentials()
    path = normalize_path(path)
    url = urljoin(BASE_URL + "/", path.lstrip("/"))
    body = None if data is None else json.dumps(data).encode("utf-8")
    headers = {
        "App-Key": app_key,
        "User-Token": user_token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if if_none_match:
        headers["If-None-Match"] = if_none_match
    request = Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            return {
                "status": response.status,
                "headers": visible_headers(response.headers),
                "body": decode_body(raw, response.headers.get("Content-Type")),
            }
    except RedirectBlockedError as exc:
        raise SystemExit(
            f"Blocked HTTP redirect to {exc.target}; credentials were not re-sent."
        ) from exc
    except HTTPError as exc:
        if exc.code == 404 and allow_not_found:
            return {"status": 404, "headers": visible_headers(exc.headers), "body": None}
        if exc.code == 304:
            return {"status": 304, "headers": visible_headers(exc.headers), "body": None}
        raw = exc.read()
        result = {
            "status": exc.code,
            "headers": visible_headers(exc.headers),
            "body": decode_body(raw, exc.headers.get("Content-Type")),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1) from exc
    except URLError as exc:
        raise SystemExit(f"Network error: {exc.reason}") from exc


def next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        match = re.match(r'\s*<([^>]+)>\s*;\s*rel="?([^";]+)"?', part)
        if match and match.group(2) == "next":
            candidate = urljoin(BASE_URL + "/", match.group(1))
            parsed = urlparse(candidate)
            if parsed.scheme != "https" or parsed.hostname != "runrun.it":
                raise SystemExit("Rejected pagination link outside https://runrun.it.")
            prefix = "/api/v1.0"
            if not parsed.path.startswith(prefix + "/") and parsed.path != prefix:
                raise SystemExit("Rejected pagination link outside /api/v1.0.")
            return parsed.path[len(prefix):] + ("?" + parsed.query if parsed.query else "")
    return None


def paginate(path: str, max_pages: int, max_items: int) -> dict[str, Any]:
    pages = 0
    items: list[Any] = []
    cut_page = False
    current: str | None = normalize_path(path)
    while current and pages < max_pages and len(items) < max_items:
        result = call("GET", current)
        pages += 1
        body = result["body"]
        if isinstance(body, list):
            remaining = max_items - len(items)
            cut_page = len(body) > remaining
            items.extend(body[:remaining])
        else:
            raise SystemExit("Paginated endpoint did not return a JSON array.")
        current = next_link(next((v for k, v in result["headers"].items() if k.lower() == "link"), None))
    return {
        "status": 200,
        "pages": pages,
        "items_returned": len(items),
        "truncated": cut_page or current is not None,
        "body": items,
    }


def emit(result: dict[str, Any]) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    request = sub.add_parser("request", help="Call one documented relative API path.")
    request.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    request.add_argument("path")
    request.add_argument("--query", action="append", default=[], metavar="KEY=VALUE")
    request.add_argument("--data", help="JSON request body.")
    request.add_argument("--if-none-match", metavar="ETAG", help="Conditional GET; 304 means unchanged.")

    pages = sub.add_parser("paginate", help="Follow bounded Link rel=next pages.")
    pages.add_argument("path")
    pages.add_argument("--query", action="append", default=[], metavar="KEY=VALUE")
    pages.add_argument("--max-pages", type=int, default=10)
    pages.add_argument("--max-items", type=int, default=1000)

    task = sub.add_parser("task", help="Task CRUD and documented actions.")
    task_sub = task.add_subparsers(dest="task_command", required=True)

    listing = task_sub.add_parser("list")
    listing.add_argument("--query", action="append", default=[], metavar="KEY=VALUE")
    listing.add_argument("--all-pages", action="store_true")
    listing.add_argument("--max-pages", type=int, default=10)
    listing.add_argument("--max-items", type=int, default=1000)

    get = task_sub.add_parser("get")
    get.add_argument("id")

    create = task_sub.add_parser("create")
    create.add_argument("--data", required=True, help="Documented JSON body.")

    update = task_sub.add_parser("update")
    update.add_argument("id")
    update.add_argument("--data", required=True, help="Documented JSON body.")

    action = task_sub.add_parser("action")
    action.add_argument("id")
    action.add_argument("action", choices=sorted(ACTIONS))
    action.add_argument("--data", help="Documented JSON body, when required.")

    delete = task_sub.add_parser("delete")
    delete.add_argument("id")
    delete.add_argument("--confirm", required=True, help="Must exactly equal the task ID.")
    return parser


def positive(value: int, name: str) -> int:
    if value < 1:
        raise SystemExit(f"{name} must be at least 1.")
    return value


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "request":
        path = add_query(args.path, parse_pairs(args.query))
        emit(call(args.method, path, parse_data(args.data), args.if_none_match))
        return
    if args.command == "paginate":
        path = add_query(args.path, parse_pairs(args.query))
        emit(paginate(path, positive(args.max_pages, "max-pages"), positive(args.max_items, "max-items")))
        return
    if args.task_command == "list":
        path = add_query("/tasks", parse_pairs(args.query))
        if args.all_pages:
            emit(paginate(path, positive(args.max_pages, "max-pages"), positive(args.max_items, "max-items")))
        else:
            emit(call("GET", path))
    elif args.task_command == "get":
        emit(call("GET", f"/tasks/{safe_id(args.id)}"))
    elif args.task_command == "create":
        emit(call("POST", "/tasks", parse_data(args.data)))
    elif args.task_command == "update":
        emit(call("PUT", f"/tasks/{safe_id(args.id)}", parse_data(args.data)))
    elif args.task_command == "action":
        emit(call("POST", f"/tasks/{safe_id(args.id)}/{args.action}", parse_data(args.data)))
    elif args.task_command == "delete":
        task_id = safe_id(args.id)
        if args.confirm != task_id:
            raise SystemExit("--confirm must exactly match the task ID.")
        emit(call("DELETE", f"/tasks/{task_id}"))


if __name__ == "__main__":
    main()
