"""Client for the LiveAgents exchange — the authority on deployed agents.

A deployed agent is the exchange's, not a terminal's. The exchange creates the sub-account, mints
the token scoped to that account alone, and asks for a container to run it; so what is running,
what it has done and whether it may keep going are all questions for the exchange. Asking a
terminal instead would be asking something that merely started it once.

Why the sub-account shape matters when reading these answers:

* Attribution is free — agent fills are on a different account from the holder's own, not
  separated by a flag somebody had to remember to set.
* An agent's token resolves to one fixed account, so a faulty agent cannot reach the master one.
* Stopping is revoking the token; stopping the container is tidying up afterwards. A container
  that misses its shutdown still cannot trade.

Market data needs no token. Anything about an account does.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

CALL_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)


class ExchangeError(Exception):
    """The exchange refused or could not answer."""

    def __init__(self, message: str, *, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status

    @property
    def unauthorized(self) -> bool:
        return self.status == 401


class NoSuchAgent(ExchangeError):
    """Nothing of the caller's answers to that name or id; ``known`` lists what does."""

    def __init__(self, needle: str, known: List[str]) -> None:
        detail = f"No agent called {needle!r}."
        if known:
            detail += f" Deployed: {', '.join(known)}."
        super().__init__(detail, status=404)
        self.needle = needle
        self.known = known


class ExchangeClient:
    """The exchange's agent API, as one holder of one token."""

    def __init__(self, base_url: str, token: str, *, client: Optional[httpx.Client] = None) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._client = client

    def _request(self, method: str, path: str, *, json_body: Any = None) -> Dict[str, Any]:
        url = f"{self._base}{path}"
        headers = {"accept": "application/json", "authorization": f"Bearer {self._token}"}
        if json_body is not None:
            headers["content-type"] = "application/json"
        try:
            if self._client is not None:
                response = self._client.request(
                    method, url, headers=headers, json=json_body, timeout=CALL_TIMEOUT)
            else:
                with httpx.Client(timeout=CALL_TIMEOUT) as client:
                    response = client.request(method, url, headers=headers, json=json_body)
        except httpx.HTTPError as exc:
            raise ExchangeError(f"{self._base} is unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise _error_from(response)
        if not response.content:
            return {}
        try:
            body = response.json()
        except ValueError as exc:
            raise ExchangeError(f"the exchange sent something that is not JSON: {exc}") from exc
        return body if isinstance(body, dict) else {"result": body}

    # ---- reading ----------------------------------------------------------

    def agents(self) -> List[Dict[str, Any]]:
        """Every agent of the caller's, with its status and metrics."""
        return list(self._request("GET", "/api/agents").get("agents") or [])

    def find(self, needle: str) -> Dict[str, Any]:
        """One agent by name or id, or :class:`NoSuchAgent` naming what does exist.

        Matching both is what the workspace's own script does, and it is what people expect: a
        name is what they chose and an id is what a log line gives them.
        """
        agents = self.agents()
        for agent in agents:
            if needle in (agent.get("name"), agent.get("id")):
                return agent
        raise NoSuchAgent(needle, [str(a.get("name") or a.get("id") or "?") for a in agents])

    def logs(self, agent_id: str) -> Dict[str, Any]:
        """An agent's stored status and its container's own output.

        Polled rather than streamed: the log lives in the agent's container, and a socket held
        open to it is a socket that keeps the container from idling out.
        """
        return self._request("GET", f"/api/agents/{_seg(agent_id)}/logs")

    def source(self, agent_id: str) -> Dict[str, Any]:
        """The code an agent was deployed with — what is running, not what is in a file locally."""
        return self._request("GET", f"/api/agents/{_seg(agent_id)}/source")

    # ---- writing ----------------------------------------------------------

    def deploy(
        self, *, name: str, market: str, source: str, mode: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create an agent: a sub-account, a token scoped to it, and a container to run it.

        ``params`` declares the tunables a supervisor may move, with ranges. Sending none is a
        deliberate choice and not an omission: an agent with no declarations gets no supervisor,
        so nothing adjusts it between deployments.
        """
        body: Dict[str, Any] = {"name": name, "market": market, "source": source, "mode": mode}
        body["params"] = params  # explicit null means "no declarations", which the exchange reads
        return self._request("POST", "/api/agents", json_body=body).get("agent") or {}

    def redeploy(
        self, agent_id: str, *, source: str, params: Optional[Dict[str, Any]] = None,
        market: str = "", mode: str = "",
    ) -> Dict[str, Any]:
        """Swap an agent's code and start it again, keeping its sub-account.

        Keeping the account is the point: a new agent for new code would strand the balance in
        the abandoned one. Fields left empty keep whatever the agent already had.
        """
        body: Dict[str, Any] = {"source": source}
        if params is not None:
            body["params"] = params
        if market:
            body["market"] = market
        if mode:
            body["mode"] = mode
        return self._request(
            "POST", f"/api/agents/{_seg(agent_id)}/redeploy", json_body=body).get("agent") or {}

    def start(self, agent_id: str) -> Dict[str, Any]:
        """Start a stopped agent, from the code it was deployed with."""
        return self._request(
            "POST", f"/api/agents/{_seg(agent_id)}/start", json_body={}).get("agent") or {}

    def stop(self, agent_id: str) -> Dict[str, Any]:
        """Stop an agent. Its sub-account and its funds are untouched."""
        return self._request("POST", f"/api/agents/{_seg(agent_id)}/stop", json_body={})


def _seg(value: str) -> str:
    """One path segment, so an id can never add a path of its own."""
    from urllib.parse import quote

    return quote(str(value), safe="")


def _error_from(response: httpx.Response) -> ExchangeError:
    detail = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = str(body.get("error") or body.get("detail") or "")
    except ValueError:
        detail = (response.text or "").strip()[:300]
    if response.status_code == 401:
        detail = detail or "that credential was not accepted"
    return ExchangeError(
        detail or f"the exchange answered {response.status_code}", status=response.status_code)
