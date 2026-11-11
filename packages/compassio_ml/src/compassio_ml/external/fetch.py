"""Bounded, rate-limited, host-allowlisted HTTPS retrieval that never overwrites a file.

* HTTPS only. ``http://`` URLs on an allowlisted host are upgraded and the original URL kept.
* Redirects are followed only to allowlisted HTTPS hosts.
* ``Content-Length`` and the streamed byte count are both checked against ``max_bytes``.
* A minimum interval is enforced between requests to the same host.
* Non-200 responses raise :class:`FetchError` and nothing is saved, so blocked or
  credential-protected sources are reported, never bypassed.
* Files are written to a temporary name and moved into place; an existing target is refused.
"""

import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.client import HTTPMessage
from pathlib import Path
from typing import IO

USER_AGENT = "compassio-research-client/0.2 (non-commercial research; bounded, rate-limited)"
CHUNK = 1 << 16


class FetchError(RuntimeError):
    """The request was refused, failed, or exceeded a limit. Nothing was saved."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True, slots=True)
class FetchLimits:
    max_bytes: int = 30 * 1024 * 1024
    timeout_s: float = 90.0
    min_interval_s: float = 1.5


@dataclass(frozen=True, slots=True)
class Retrieval:
    """Provenance of one saved response."""

    requested_url: str
    fetched_url: str
    final_url: str
    retrieved_at: str
    http_status: int
    content_type: str | None
    bytes: int
    sha256: str
    path: Path

    def as_record(self, relative_to: Path) -> dict[str, object]:
        return {
            "requested_url": self.requested_url,
            "fetched_url": self.fetched_url,
            "final_url": self.final_url,
            "retrieved_at": self.retrieved_at,
            "http_status": self.http_status,
            "content_type": self.content_type,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "file": self.path.relative_to(relative_to).as_posix(),
        }


def _host(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


class _AllowlistRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed: frozenset[str]) -> None:
        self.allowed = allowed

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        parts = urllib.parse.urlsplit(newurl)
        if parts.scheme != "https" or (parts.hostname or "").lower() not in self.allowed:
            raise FetchError(f"Redirect to non-allowlisted or non-HTTPS URL refused: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


Opener = Callable[[urllib.request.Request, float], IO[bytes]]


@dataclass
class SafeFetcher:
    allowed_hosts: frozenset[str]
    limits: FetchLimits = field(default_factory=FetchLimits)
    user_agent: str = USER_AGENT
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    opener: Opener | None = None
    _last_request: dict[str, float] = field(default_factory=dict)

    def normalise_url(self, url: str) -> str:
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower()
        if host not in self.allowed_hosts:
            raise FetchError(f"Host not allowlisted: {host or url}")
        if parts.scheme == "http":
            parts = parts._replace(scheme="https")
        elif parts.scheme != "https":
            raise FetchError(f"Only HTTPS is allowed: {url}")
        path = urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
        return urllib.parse.urlunsplit(parts._replace(path=path))

    def _wait(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            remaining = self.limits.min_interval_s - (self.clock() - last)
            if remaining > 0:
                self.sleep(remaining)
        self._last_request[host] = self.clock()

    def _open(self, request: urllib.request.Request) -> IO[bytes]:
        if self.opener is not None:
            return self.opener(request, self.limits.timeout_s)
        opener = urllib.request.build_opener(_AllowlistRedirect(self.allowed_hosts))
        response: IO[bytes] = opener.open(request, timeout=self.limits.timeout_s)
        return response

    def fetch(self, url: str, dest: Path, *, max_bytes: int | None = None) -> Retrieval:
        """Download ``url`` to ``dest`` (which must not exist). Raises ``FetchError``."""
        if dest.exists():
            raise FetchError(f"Refusing to overwrite existing file: {dest}")
        limit = max_bytes if max_bytes is not None else self.limits.max_bytes
        fetched_url = self.normalise_url(url)
        self._wait(_host(fetched_url))
        request = urllib.request.Request(
            fetched_url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"}
        )
        retrieved_at = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            response = self._open(request)
        except urllib.error.HTTPError as exc:
            raise FetchError(f"HTTP {exc.code} for {fetched_url}", status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise FetchError(f"Network error for {fetched_url}: {exc.reason}") from exc

        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".partial")
        digest = hashlib.sha256()
        size = 0
        try:
            status = int(getattr(response, "status", 200))
            if status != 200:
                raise FetchError(f"HTTP {status} for {fetched_url}", status=status)
            headers = getattr(response, "headers", None)
            declared = headers.get("Content-Length") if headers is not None else None
            if declared is not None and declared.isdigit() and int(declared) > limit:
                raise FetchError(f"Declared size {declared} exceeds limit {limit}: {fetched_url}")
            content_type = headers.get("Content-Type") if headers is not None else None
            final_url = str(getattr(response, "url", fetched_url))
            with tmp.open("xb") as handle:
                while chunk := response.read(CHUNK):
                    size += len(chunk)
                    if size > limit:
                        raise FetchError(f"Response exceeded {limit} bytes: {fetched_url}")
                    digest.update(chunk)
                    handle.write(chunk)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        finally:
            response.close()
        tmp.replace(dest)
        return Retrieval(
            requested_url=url,
            fetched_url=fetched_url,
            final_url=final_url,
            retrieved_at=retrieved_at,
            http_status=status,
            content_type=content_type,
            bytes=size,
            sha256=digest.hexdigest(),
            path=dest,
        )
