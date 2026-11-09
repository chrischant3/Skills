#!/usr/bin/env python3
"""HTTP plumbing shared by the REST fallbacks (Jira and source control). Standard library only.

A transport is any callable(method, url, headers, body, timeout) -> (status, headers, body
bytes). Scripts use urllib_transport; tests pass one that replays recorded responses, so
no test touches the network.
"""

import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime

DEFAULT_RETRY_AFTER = 10


def urllib_transport(method, url, headers, body, timeout):
    """Send one HTTP request. Returns (status, headers, body bytes); HTTP errors are returned, not raised."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers or {}), err.read() or b""


def header(headers: dict, name: str):
    """Return a response header's value, ignoring case, or None."""
    return next((v for k, v in headers.items() if k.lower() == name.lower()), None)


def retry_after(headers: dict) -> int:
    """Seconds to wait after HTTP 429, from Retry-After (seconds or an HTTP date), else DEFAULT_RETRY_AFTER."""
    value = header(headers, "Retry-After")
    if value is None:
        return DEFAULT_RETRY_AFTER
    try:
        return max(0, int(value))
    except ValueError:
        try:
            return max(0, int(parsedate_to_datetime(value).timestamp() - time.time()))
        except (TypeError, ValueError):
            return DEFAULT_RETRY_AFTER
