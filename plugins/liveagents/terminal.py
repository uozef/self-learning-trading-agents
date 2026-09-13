"""Client for the Agent Terminal console API — the surface that builds and deploys agents.

The console at liveagents.org drives the same endpoints from a browser; this is the same client
from a server. The division of labour is deliberate: the workspace owns what an agent is, and this
carries a request in and the answer out.

Authentication is a bearer token, never a cookie. Agent Terminal authenticates its own page with
an HttpOnly cookie, which cannot travel here; a bearer is handed over deliberately and the browser
never attaches it on its own, so a caller that was not given one cannot act as the holder.

Building and deploying stream newline-delimited JSON because they take a minute or two. Every
event is yielded as it arrives, so a caller can show progress rather than waiting in silence —
which matters more than it sounds: a person who reloads a deploy ends up with two of the same
agent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

import httpx

# A build runs Claude Code against the harness, which is minutes, not seconds. The read timeout
# has to outlast that; connect stays short so an unreachable host fails quickly.
BUILD_TIMEOUT = httpx.Timeout(connect=10.0, read=900.0, write=30.0, pool=10.0)
CALL_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


class TerminalError(Exception):
    """The workspace refused or could not answer. ``status`` is the HTTP status when there was one."""

    def __init__(self, message: str, *, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status

    @property
    def unauthorized(self) -> bool:
        """Whether the credential was rejected, as opposed to the request being wrong."""
        return self.status == 401


@dataclass(frozen=True)
class AgentKind:
    """A template the workspace will actually build from."""

    id: str
    label: str
    brief: str = ""


class TerminalClient:
    """The console API of one Agent Terminal deployment, as one holder of one token."""

    def __init__(self, base_url: str, token: str, *, client: Optional[httpx.Client] = None) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._client = client

    # ---- plumbing ---------------------------------------------------------

    def _headers(self, *, json_body: bool = False) -> Dict[str, str]:
        headers = {"accept": "application/json", "authorization": f"Bearer {self._token}"}
        if json_body:
            headers["content-type"] = "application/json"
        return headers

    def _request(self, method: str, path: str, *, json_body: Any = None) -> Any:
        url = f"{self._base}{path}"
        try:
            if self._client is not None:
                response = self._client.request(
                    method, url, headers=self._headers(json_body=json_body is not None),
                    json=json_body, timeout=CALL_TIMEOUT)
            else:
                with httpx.Client(timeout=CALL_TIMEOUT) as client:
                    response = client.request(
                        method, url, headers=self._headers(json_body=json_body is not None),
                        json=json_body)
        except httpx.HTTPError as exc:
            raise TerminalError(f"{self._base} is unreachable: {exc}") from exc
        return _decode(response)

    def _stream(self, path: str, body: Any) -> Iterator[Dict[str, Any]]:
        """POST *body* and yield one dict per line of the NDJSON response.

        A line that is not JSON is the process talking rather than the protocol, so it is yielded
        as output instead of being dropped — that is where a build's real error message usually
        is.
        """
        url = f"{self._base}{path}"
        try:
            if self._client is not None:
                context = self._client.stream(
                    "POST", url, headers=self._headers(json_body=True), json=body,
                    timeout=BUILD_TIMEOUT)
                owned = None
            else:
                owned = httpx.Client(timeout=BUILD_TIMEOUT)
                context = owned.stream(
                    "POST", url, headers=self._headers(json_body=True), json=body)
            try:
                with context as response:
                    if response.status_code >= 400:
                        response.read()
                        raise _error_from(response)
                    for line in response.iter_lines():
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                        except ValueError:
                            yield {"stream": "stdout", "text": line}
                            continue
                        yield event if isinstance(event, dict) else {"stream": "stdout", "text": line}
            finally:
                if owned is not None:
                    owned.close()
        except httpx.HTTPError as exc:
            raise TerminalError(f"{self._base} is unreachable: {exc}") from exc

    # ---- who is calling ---------------------------------------------------

    def whoami(self) -> Dict[str, Any]:
        """The account the workspace thinks we are, and whether Claude is signed in for it.

        ``sharedCredentialReady`` is the one to check before offering to build: nothing builds
        without a Claude credential, and finding that out after a two-minute wait is worse than
        being told up front.
        """
        return self._request("GET", "/api/whoami")

    # ---- building ---------------------------------------------------------

    def kinds(self) -> Dict[str, Any]:
        """The templates available, and whether the workspace could build right now."""
        return self._request("GET", "/api/build/kinds")

    def source(self, file: str) -> Dict[str, Any]:
        """One agent's source, as the workspace holds it."""
        return self._request("GET", f"/api/build/source?file={_quote(file)}")

    def build(
        self, *, idea: str, market: str, kind: str, name: str, interval_seconds: int,
        description: str = "",
    ) -> Iterator[Dict[str, Any]]:
        """Write a new agent in the workspace, streaming what happens as it happens."""
        return self._stream("/api/build", {
            "idea": idea,
            "description": description,
            "market": market,
            "kind": kind,
            "name": name,
            "intervalSeconds": interval_seconds,
        })

    def deploy(
        self, *, name: str, market: str, mode: str, exchange_token: str = "",
    ) -> Iterator[Dict[str, Any]]:
        """Deploy an agent the workspace already holds, streaming the deploy.

        ``exchange_token`` is sent for this deploy and nothing else. A deploy creates a
        sub-account, which is an act on the exchange in the holder's name, and the terminal holds
        no exchange token for anybody — so the caller's own has to travel with the request.
        """
        body: Dict[str, Any] = {"name": name, "market": market, "mode": mode}
        if exchange_token:
            body["exchangeToken"] = exchange_token
        return self._stream("/api/build/deploy", body)

    # ---- backtesting ------------------------------------------------------

    def backtest(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Replay a strategy in the workspace. The replayed ``decide`` is the one that trades live."""
        return self._request("POST", "/api/backtest", json_body=request)

    def backtests(self) -> Dict[str, Any]:
        """The saved runs, as files in the workspace the user can read and delete."""
        return self._request("GET", "/api/backtests")

    def backtest_read(self, file: str) -> Dict[str, Any]:
        """One saved run."""
        return self._request("GET", f"/api/backtests/read?file={_quote(file)}")

    def agents(self) -> Dict[str, Any]:
        """What the workspace knows about the caller's agents."""
        return self._request("GET", "/api/agents")


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


#: What to do about a 401, which is almost always the same thing.
#:
#: The workspace rejects a credential for one of two reasons and only one of them is interesting.
#: A revoked workspace key is deliberate. A copied browser token is not: it is the console's Privy
#: access token, it lives an hour, and until workspace keys existed it was the only thing there was
#: to copy — so the overwhelmingly likely cause of a 401 here is a setup that was correct when it
#: was made and expired the same afternoon. Saying so costs two lines and saves the hour somebody
#: would otherwise spend checking a token that is not wrong, merely finished.
REFRESH_ADVICE = (
    "Set LIVEAGENTS_TERMINAL_TOKEN to a workspace key: sign in at the console, open "
    "Connect Claude Code, and create one under Workspace keys. Keys start with `lat_`, "
    "survive signing out, and are revocable. A token copied out of browser storage is a "
    "browser session and expires within the hour."
)


def _error_from(response: httpx.Response) -> TerminalError:
    """The server's own message when it sent one, and the status when it did not."""
    detail = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = str(body.get("error") or body.get("detail") or "")
    except ValueError:
        detail = (response.text or "").strip()[:300]
    if response.status_code == 401:
        detail = detail or "that credential was not accepted"
        detail = f"{detail}. {REFRESH_ADVICE}"
    return TerminalError(
        detail or f"the workspace answered {response.status_code}", status=response.status_code)


def _decode(response: httpx.Response) -> Any:
    if response.status_code >= 400:
        raise _error_from(response)
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise TerminalError(f"the workspace sent something that is not JSON: {exc}") from exc
