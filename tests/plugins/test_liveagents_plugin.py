"""Tests for the LiveAgents plugin: the two clients, the CLI surface, and registration.

No live network — every request is served by an ``httpx.MockTransport``, so what is asserted is
the contract with each host: the URL, the bearer, the body sent, and what a caller is told when
the answer is a refusal rather than a result.

The split under test is the one the design rests on. Authoring and backtests go to the workspace;
the agent lifecycle goes to the exchange. A test that let either answer the other's question would
pass while the integration was wrong.
"""

from __future__ import annotations

import argparse
import json

import httpx
import pytest

from plugins.liveagents import cli as la_cli
from plugins.liveagents import config as la_config
from plugins.liveagents.config import LiveAgentsConfig, MissingToken, load_config
from plugins.liveagents.exchange import ExchangeClient, ExchangeError, NoSuchAgent
from plugins.liveagents.terminal import TerminalClient, TerminalError

TERMINAL = "https://terminal.example.test"
EXCHANGE = "https://dex.example.test"
PLATFORM = "https://platform.example.test/api"


def _seen(store):
    """A transport that records each request and replies from *store*'s handler."""

    def handler(request: httpx.Request) -> httpx.Response:
        store.append(request)
        return store.reply(request)

    return httpx.MockTransport(handler)


class Recorder(list):
    def __init__(self, reply):
        super().__init__()
        self.reply = reply


def _terminal_client(reply) -> tuple[TerminalClient, Recorder]:
    recorder = Recorder(reply)
    client = httpx.Client(transport=_seen(recorder))
    return TerminalClient(TERMINAL, "tok-terminal", client=client), recorder


def _exchange_client(reply, *, platform: str = PLATFORM) -> tuple[ExchangeClient, Recorder]:
    recorder = Recorder(reply)
    client = httpx.Client(transport=_seen(recorder))
    return ExchangeClient(
        EXCHANGE, "tok-exchange", client=client, platform_url=platform), recorder


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults_point_at_the_platform(self):
        cfg = load_config(None, env={})
        assert cfg.terminal_url == la_config.DEFAULT_TERMINAL_URL
        assert cfg.exchange_url == la_config.DEFAULT_EXCHANGE_URL
        assert cfg.console_url == la_config.DEFAULT_CONSOLE_URL

    def test_tokens_come_from_the_environment(self):
        cfg = load_config(None, env={
            la_config.TERMINAL_TOKEN_ENV: " workspace-token ",
            la_config.EXCHANGE_TOKEN_ENV: "exchange-token",
        })
        assert cfg.require_terminal_token() == "workspace-token"
        assert cfg.require_exchange_token() == "exchange-token"

    def test_urls_come_from_settings_and_lose_a_trailing_slash(self):
        settings = {"terminal_url": "https://t.example.test/", "exchange_url": "https://d.example.test"}
        cfg = load_config(lambda key, default: settings.get(key, default), env={})
        assert cfg.terminal_url == "https://t.example.test"
        assert cfg.exchange_url == "https://d.example.test"

    def test_a_blank_setting_falls_back_to_the_default(self):
        cfg = load_config(lambda key, default: "" if key == "terminal_url" else default, env={})
        assert cfg.terminal_url == la_config.DEFAULT_TERMINAL_URL

    def test_a_broken_settings_reader_does_not_break_a_command(self):
        def explode(key, default):
            raise RuntimeError("malformed config")

        assert load_config(explode, env={}).terminal_url == la_config.DEFAULT_TERMINAL_URL

    def test_a_missing_token_says_which_variable_to_set(self):
        cfg = load_config(None, env={})
        with pytest.raises(MissingToken) as terminal:
            cfg.require_terminal_token()
        assert la_config.TERMINAL_TOKEN_ENV in str(terminal.value)
        with pytest.raises(MissingToken) as exchange:
            cfg.require_exchange_token()
        assert la_config.EXCHANGE_TOKEN_ENV in str(exchange.value)


# ---------------------------------------------------------------------------
# The workspace client
# ---------------------------------------------------------------------------


class TestTerminalClient:
    def test_calls_carry_the_bearer_and_never_a_cookie(self):
        client, seen = _terminal_client(lambda r: httpx.Response(200, json={"wallet": "did:privy:1"}))
        client.whoami()
        assert seen[0].headers["authorization"] == "Bearer tok-terminal"
        # Agent Terminal authenticates its own page with a cookie; a cookie cannot travel here,
        # and a browser would attach it to every request. A bearer is handed over deliberately.
        assert "cookie" not in seen[0].headers

    def test_kinds_reads_the_workspace_templates(self):
        payload = {"kinds": [{"id": "momentum", "label": "Momentum"}], "claudeReady": True}
        client, seen = _terminal_client(lambda r: httpx.Response(200, json=payload))
        assert client.kinds()["kinds"][0]["id"] == "momentum"
        assert seen[0].url.path == "/api/build/kinds"

    def test_source_and_backtest_read_escape_the_filename(self):
        client, seen = _terminal_client(lambda r: httpx.Response(200, json={}))
        client.source("agents/my agent.mjs")
        client.backtest_read("runs/one two.json")
        # An unescaped space or slash would be a different path, or no path at all.
        assert "my%20agent.mjs" in str(seen[0].url)
        assert "one%20two.json" in str(seen[1].url)

    def test_build_sends_the_wizards_own_field_names(self):
        # The workspace reads these names; renaming one here silently builds nothing.
        client, seen = _terminal_client(
            lambda r: httpx.Response(200, content=b'{"done":true,"code":0}\n'))
        list(client.build(
            idea="buy strength", market="BTC-PERP", kind="momentum", name="My Agent",
            interval_seconds=30, description="longer brief"))
        body = json.loads(seen[0].content)
        assert body == {
            "idea": "buy strength", "description": "longer brief", "market": "BTC-PERP",
            "kind": "momentum", "name": "My Agent", "intervalSeconds": 30}

    def test_deploy_sends_the_exchange_token_only_when_there_is_one(self):
        client, seen = _terminal_client(
            lambda r: httpx.Response(200, content=b'{"done":true,"code":0}\n'))
        list(client.deploy(name="a", market="BTC-PERP", mode="demo"))
        assert "exchangeToken" not in json.loads(seen[0].content)
        list(client.deploy(name="a", market="BTC-PERP", mode="live", exchange_token="ex-tok"))
        assert json.loads(seen[1].content)["exchangeToken"] == "ex-tok"

    def test_a_stream_yields_one_event_per_line(self):
        lines = b'{"type":"claude","event":{"type":"start"}}\n{"text":"writing"}\n{"done":true,"code":0}\n'
        client, _ = _terminal_client(lambda r: httpx.Response(200, content=lines))
        events = list(client.build(
            idea="i", market="m", kind="k", name="n", interval_seconds=60))
        assert [e.get("type") or e.get("text") or e.get("done") for e in events] == [
            "claude", "writing", True]

    def test_a_non_json_line_is_the_process_talking_not_a_dropped_line(self):
        # This is where a build's real error message usually is.
        client, _ = _terminal_client(
            lambda r: httpx.Response(200, content=b'npm ERR! missing script\n{"error":"build failed"}\n'))
        events = list(client.build(idea="i", market="m", kind="k", name="n", interval_seconds=60))
        assert events[0] == {"stream": "stdout", "text": "npm ERR! missing script"}
        assert events[1]["error"] == "build failed"

    def test_the_workspaces_own_message_is_what_the_caller_is_told(self):
        client, _ = _terminal_client(
            lambda r: httpx.Response(400, json={"error": "no such agent kind"}))
        with pytest.raises(TerminalError) as err:
            client.kinds()
        assert "no such agent kind" in str(err.value)

    def test_a_rejected_credential_is_distinguishable(self):
        client, _ = _terminal_client(lambda r: httpx.Response(401, json={"error": "unauthorized"}))
        with pytest.raises(TerminalError) as err:
            client.whoami()
        assert err.value.unauthorized is True

    def test_an_error_status_on_a_stream_is_raised_not_yielded(self):
        client, _ = _terminal_client(lambda r: httpx.Response(401, json={"error": "unauthorized"}))
        with pytest.raises(TerminalError) as err:
            list(client.deploy(name="a", market="m", mode="live"))
        assert err.value.unauthorized is True

    def test_an_unreachable_host_says_so_rather_than_raising_httpx(self):
        def refuse(request):
            raise httpx.ConnectError("connection refused")

        client = TerminalClient(
            TERMINAL, "tok", client=httpx.Client(transport=httpx.MockTransport(refuse)))
        with pytest.raises(TerminalError) as err:
            client.whoami()
        assert TERMINAL in str(err.value)


# ---------------------------------------------------------------------------
# The exchange client
# ---------------------------------------------------------------------------


def _agent(**over):
    base = {
        "id": "ag_1", "name": "momentum", "mode": "live", "status": "running",
        "market": "BTC-PERP", "accountId": 42, "equity": "100",
        "metrics": {"trades": 3, "netPnl": "1.5", "maxDrawdown": "0.2"},
    }
    base.update(over)
    return base


class TestExchangeClient:
    def test_agents_come_back_as_a_list(self):
        client, seen = _exchange_client(
            lambda r: httpx.Response(200, json={"agents": [_agent()]}))
        assert [a["name"] for a in client.agents()] == ["momentum"]
        assert seen[0].headers["authorization"] == "Bearer tok-exchange"

    def test_an_empty_account_is_an_empty_list_not_an_error(self):
        client, _ = _exchange_client(lambda r: httpx.Response(200, json={}))
        assert client.agents() == []

    def test_find_matches_a_name_or_an_id(self):
        client, _ = _exchange_client(lambda r: httpx.Response(200, json={"agents": [_agent()]}))
        assert client.find("momentum")["id"] == "ag_1"
        assert client.find("ag_1")["name"] == "momentum"

    def test_an_unknown_name_says_what_does_exist(self):
        client, _ = _exchange_client(lambda r: httpx.Response(200, json={"agents": [_agent()]}))
        with pytest.raises(NoSuchAgent) as err:
            client.find("typo")
        assert "momentum" in str(err.value)

    def test_deploy_sends_the_agent_record_the_exchange_expects(self):
        client, seen = _exchange_client(
            lambda r: httpx.Response(200, json={"agent": _agent(status="starting")}))
        client.deploy(
            name="momentum", market="BTC-PERP", source="export const decide = () => {}",
            mode="live", params={"tunables": {"threshold": [1, 5]}})
        body = json.loads(seen[0].content)
        assert body["name"] == "momentum"
        assert body["mode"] == "live"
        assert body["params"]["tunables"]["threshold"] == [1, 5]

    def test_deploying_without_declarations_sends_an_explicit_none(self):
        # An agent that declares no tunables gets no supervisor, and that is a choice the
        # exchange has to be told about rather than left to infer from an absent field.
        client, seen = _exchange_client(lambda r: httpx.Response(200, json={"agent": _agent()}))
        client.deploy(name="a", market="m", source="x", mode="demo")
        assert json.loads(seen[0].content)["params"] is None

    def test_redeploy_leaves_out_what_should_stay_as_it_was(self):
        client, seen = _exchange_client(lambda r: httpx.Response(200, json={"agent": _agent()}))
        client.redeploy("ag_1", source="new code")
        body = json.loads(seen[0].content)
        assert body == {"source": "new code"}
        assert seen[0].url.path == "/api/agents/ag_1/redeploy"

    def test_an_id_cannot_add_a_path_of_its_own(self):
        client, seen = _exchange_client(lambda r: httpx.Response(200, json={}))
        client.logs("../../admin")
        # ``raw_path`` is what goes on the wire; ``.path`` decodes for display and would show
        # the traversal as though it had happened.
        assert seen[0].url.raw_path == b"/api/agents/..%2F..%2Fadmin/logs"

    def test_stop_and_start_hit_their_own_routes(self):
        client, seen = _exchange_client(
            lambda r: httpx.Response(200, json={"agent": _agent(), "runnerStopped": True}))
        client.stop("ag_1")
        client.start("ag_1")
        assert [str(r.url.path) for r in seen] == [
            "/api/agents/ag_1/stop", "/api/agents/ag_1/start"]

    def test_funding_is_a_request_to_the_platform_and_not_a_transfer(self):
        # The one thing worth proving about this call: where it goes, what it carries, and that
        # it is not the exchange's transfer route. A funding request moves nothing.
        client, seen = _exchange_client(
            lambda r: httpx.Response(201, json={"request": {"id": "fr_1", "status": "pending"}}))
        answer = client.request_funding("ag_1", amount="250", note="out of margin")
        assert answer["request"]["status"] == "pending"
        assert str(seen[0].url) == f"{PLATFORM}/agents/fund-requests"
        assert seen[0].headers["authorization"] == "Bearer tok-exchange"
        body = json.loads(seen[0].content)
        assert body == {
            "agentId": "ag_1", "source": "hermes", "amount": "250", "note": "out of margin"}

    def test_funding_without_an_amount_leaves_the_figure_to_the_owner(self):
        client, seen = _exchange_client(lambda r: httpx.Response(201, json={"request": {}}))
        client.request_funding("ag_1")
        assert json.loads(seen[0].content) == {"agentId": "ag_1", "source": "hermes"}

    def test_funding_says_so_when_there_is_nowhere_to_send_it(self):
        client, seen = _exchange_client(lambda r: httpx.Response(201, json={}), platform="")
        with pytest.raises(ExchangeError):
            client.request_funding("ag_1")
        assert not seen, "nothing should have been sent"

    def test_the_exchanges_own_message_is_what_the_caller_is_told(self):
        client, _ = _exchange_client(
            lambda r: httpx.Response(402, json={"error": "no free collateral"}))
        with pytest.raises(ExchangeError) as err:
            client.agents()
        assert "no free collateral" in str(err.value)


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------


def _parse(argv):
    parser = argparse.ArgumentParser(prog="liveagents")
    la_cli.register_cli(parser)
    return parser.parse_args(argv)


class TestCliSurface:
    def test_every_agent_terminal_operation_has_a_subcommand(self):
        # The skills call these names; a rename here breaks every skill at once.
        expected = {
            "whoami", "launch", "kinds", "build", "publish", "backtest", "backtests",
            "backtest-read", "agents", "logs", "source", "start", "stop", "redeploy",
            "fund-agent",
        }
        assert expected <= set(la_cli._COMMANDS)

    def test_build_requires_the_fields_a_workspace_cannot_guess(self):
        for missing in (
            ["build", "--market", "BTC-PERP", "--kind", "k", "--name", "n"],   # no idea
            ["build", "--idea", "i", "--kind", "k", "--name", "n"],            # no market
            ["build", "--idea", "i", "--market", "m", "--name", "n"],          # no kind
            ["build", "--idea", "i", "--market", "m", "--kind", "k"],          # no name
        ):
            with pytest.raises(SystemExit):
                _parse(missing)

    def test_mode_is_demo_unless_live_is_asked_for(self):
        # The safe one is the default: demo runs for real and the exchange refuses its orders.
        assert _parse(["publish", "a", "--market", "m"]).mode == "demo"
        assert _parse(["publish", "a", "--market", "m", "--mode", "live"]).mode == "live"

    def test_a_mode_that_is_neither_is_refused(self):
        with pytest.raises(SystemExit):
            _parse(["publish", "a", "--market", "m", "--mode", "yolo"])

    def test_funding_takes_an_optional_agent_and_an_optional_amount(self):
        # Both optional on purpose: the newest agent is what "fund what I just deployed" means,
        # and the amount belongs to whoever can see their own free balance.
        bare = _parse(["fund-agent"])
        assert bare.name == "" and bare.amount == "" and bare.wait is True
        named = _parse(["fund-agent", "momentum", "--amount", "250", "--no-wait"])
        assert named.name == "momentum" and named.amount == "250" and named.wait is False

    def test_funding_refuses_an_amount_that_is_not_a_positive_number(self, monkeypatch, capsys):
        monkeypatch.setenv(la_config.EXCHANGE_TOKEN_ENV, "tok")
        monkeypatch.setattr(
            la_cli.ExchangeClient, "agents", lambda self: [_agent()], raising=True)
        code = la_cli.dispatch(_parse(["fund-agent", "momentum", "--amount", "-5"]))
        assert code == 2
        assert "positive" in capsys.readouterr().err

    def test_an_unknown_subcommand_is_an_exit_code_not_a_traceback(self):
        args = argparse.Namespace(liveagents_command="teleport", json=False, token=None)
        assert la_cli.dispatch(args) == 2

    def test_a_missing_credential_exits_two_and_names_the_variable(self, monkeypatch, capsys):
        monkeypatch.delenv(la_config.TERMINAL_TOKEN_ENV, raising=False)
        monkeypatch.delenv(la_config.EXCHANGE_TOKEN_ENV, raising=False)
        assert la_cli.dispatch(_parse(["whoami"])) == 2
        assert la_config.TERMINAL_TOKEN_ENV in capsys.readouterr().err

    def test_a_live_publish_without_an_exchange_session_is_refused_before_anything_runs(
            self, monkeypatch, capsys):
        # A live deploy creates a sub-account in the holder's name; the terminal holds no token
        # for anybody, so finding this out from a failed deploy would be finding out too late.
        monkeypatch.setenv(la_config.TERMINAL_TOKEN_ENV, "workspace-token")
        monkeypatch.delenv(la_config.EXCHANGE_TOKEN_ENV, raising=False)
        code = la_cli.dispatch(_parse(["publish", "a", "--market", "m", "--mode", "live"]))
        assert code == 2
        assert la_config.EXCHANGE_TOKEN_ENV in capsys.readouterr().err

    def test_token_on_the_command_line_serves_whichever_host_is_called(self, monkeypatch):
        monkeypatch.delenv(la_config.TERMINAL_TOKEN_ENV, raising=False)
        monkeypatch.delenv(la_config.EXCHANGE_TOKEN_ENV, raising=False)
        cfg = la_cli._config(_parse(["--token", "one-token", "agents"]))
        assert cfg.require_terminal_token() == "one-token"
        assert cfg.require_exchange_token() == "one-token"

    def test_param_overrides_want_name_equals_value(self, monkeypatch, capsys):
        monkeypatch.setenv(la_config.TERMINAL_TOKEN_ENV, "t")
        code = la_cli.dispatch(_parse(["backtest", "a", "--param", "justaname"]))
        assert code == 2
        assert "NAME=VALUE" in capsys.readouterr().err


def _run_artifact(**over):
    """The shape the workspace actually saves, verified against its own handler."""
    run = {
        "id": "momentum-1788698370000", "agent": "agents/momentum.mjs", "strategy": "momentum",
        "market": "BTC-PERP", "interval": "5m", "days": 7, "barCount": 2016,
        "summary": {
            "trades": 41, "netPnl": "-15930.71", "feesPaid": "19963.21", "returnPct": -259.1,
            "maxDrawdown": "25911.31", "maxDrawdownPct": 259.1, "sharpe": None, "winRate": 0.4,
        },
    }
    run.update(over)
    return run


class TestBacktestContract:
    """The field names the workspace reads. One it does not read is an override silently dropped."""

    def test_parameter_overrides_are_sent_as_set(self, monkeypatch, capsys):
        monkeypatch.setenv(la_config.TERMINAL_TOKEN_ENV, "t")
        seen = []

        def transport(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={"run": _run_artifact()})

        monkeypatch.setattr(
            la_cli, "_terminal",
            lambda args: TerminalClient(
                TERMINAL, "t", client=httpx.Client(transport=httpx.MockTransport(transport))))
        la_cli.dispatch(_parse([
            "backtest", "agents/momentum.mjs", "--param", "fast=8", "--param", "slow=34"]))
        # `params` would be accepted by the route and ignored by the container.
        assert seen[0]["set"] == {"fast": "8", "slow": "34"}
        assert "params" not in seen[0]

    def test_the_window_and_cost_knobs_travel_under_their_own_names(self, monkeypatch):
        monkeypatch.setenv(la_config.TERMINAL_TOKEN_ENV, "t")
        seen = []

        def transport(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={"run": _run_artifact()})

        monkeypatch.setattr(
            la_cli, "_terminal",
            lambda args: TerminalClient(
                TERMINAL, "t", client=httpx.Client(transport=httpx.MockTransport(transport))))
        la_cli.dispatch(_parse([
            "backtest", "agents/a.mjs", "--from", "2022-01-01", "--to", "2024-01-01",
            "--interval", "5m", "--market", "ETH-PERP", "--fee", "0.02", "--equity", "5000"]))
        body = seen[0]
        assert body["from"] == "2022-01-01" and body["to"] == "2024-01-01"
        assert body["interval"] == "5m" and body["market"] == "ETH-PERP"
        assert body["fee"] == "0.02" and body["equity"] == "5000"
        # An unset window is not sent at all, so the workspace keeps its own default.
        assert "days" not in body and "dataset" not in body


class TestRunRendering:
    def test_net_pnl_comes_before_the_win_rate(self):
        text = la_cli._render_run(_run_artifact(), "agents/momentum.mjs")
        # The win rate is the most flattering number available and must never lead.
        assert text.index("net P&L") < text.index("win rate")

    def test_fees_are_shown_next_to_the_result(self):
        text = la_cli._render_run(_run_artifact(), "a")
        assert "fees paid" in text

    def test_an_absent_sharpe_says_why(self):
        text = la_cli._render_run(_run_artifact(), "a")
        assert "n/a (too few samples)" in text

    def test_a_thin_sample_is_called_out(self):
        text = la_cli._render_run(
            _run_artifact(summary={"trades": 4, "netPnl": "1"}), "a")
        assert "too few to be significant" in text

    def test_a_healthy_sample_is_not_called_out(self):
        text = la_cli._render_run(
            _run_artifact(summary={"trades": 120, "netPnl": "1"}), "a")
        assert "too few to be significant" not in text

    def test_the_run_id_is_quoted_so_the_result_can_be_checked(self):
        text = la_cli._render_run(_run_artifact(), "a")
        assert "momentum-1788698370000" in text

    def test_the_real_window_is_reported_not_the_requested_one(self):
        dated = la_cli._render_run(
            _run_artifact(**{"from": "2022-01-01", "to": "2024-01-01"}), "a")
        assert "2022-01-01 → 2024-01-01" in dated
        assert "2016" in dated  # the bars it actually got

    def test_an_empty_answer_is_reported_as_empty(self):
        assert "no run" in la_cli._render_run({}, "a").lower()


class TestLaunchUrl:
    """The handoff that opens Agent Terminal already signed in."""

    def test_the_token_travels_in_the_fragment(self, monkeypatch, capsys):
        monkeypatch.setenv(la_config.TERMINAL_TOKEN_ENV, "privy-id-token")
        assert la_cli.dispatch(_parse(["launch"])) == 0
        url = capsys.readouterr().out.strip()
        # A fragment never reaches a server and never appears in a Referer, which is the only
        # reason a credential may be passed this way.
        assert "#sso=privy-id-token" in url
        assert "?" not in url

    def test_the_who_tag_is_carried_and_escaped(self, monkeypatch, capsys):
        monkeypatch.setenv(la_config.TERMINAL_TOKEN_ENV, "t")
        la_cli.dispatch(_parse(["launch", "--as", "did:privy:abc"]))
        # A changed tag is how a shared browser signs the previous person out.
        assert "as=did%3Aprivy%3Aabc" in capsys.readouterr().out

    def test_it_points_at_the_configured_terminal(self, monkeypatch, capsys):
        monkeypatch.setenv(la_config.TERMINAL_TOKEN_ENV, "t")
        la_cli.dispatch(_parse(["--token", "t", "launch"]))
        assert capsys.readouterr().out.strip().startswith(la_config.DEFAULT_TERMINAL_URL)

    def test_without_a_credential_there_is_no_url(self, monkeypatch, capsys):
        monkeypatch.delenv(la_config.TERMINAL_TOKEN_ENV, raising=False)
        assert la_cli.dispatch(_parse(["launch"])) == 2
        assert not capsys.readouterr().out.strip()


class TestCliRendering:
    def test_an_empty_account_reads_as_empty_rather_than_broken(self):
        assert la_cli._render_agents([]) == "No agents deployed yet."

    def test_a_stored_error_is_shown_under_its_agent(self):
        text = la_cli._render_agents([_agent(lastError="strategy returned, so it was a crash")])
        assert "momentum" in text
        assert "strategy returned" in text

    def test_a_finished_stream_exits_zero(self, capsys):
        assert la_cli._stream_to_stdout(iter([{"done": True, "code": 0}]), as_json=False) == 0

    def test_a_failed_stream_exits_one(self, capsys):
        assert la_cli._stream_to_stdout(iter([{"error": "build failed"}]), as_json=False) == 1
        assert "build failed" in capsys.readouterr().out

    def test_a_nonzero_exit_in_the_stream_is_a_failure(self):
        assert la_cli._stream_to_stdout(iter([{"done": True, "code": 2}]), as_json=False) == 1

    def test_a_truncated_stream_is_not_reported_as_success(self, capsys):
        # Silence is the dangerous case: a caller that reads it as success runs the deploy again
        # and ends up with two of the same agent.
        assert la_cli._stream_to_stdout(iter([{"text": "working"}]), as_json=False) == 1
        assert "without saying whether it finished" in capsys.readouterr().err

    def test_json_mode_emits_one_object_per_line(self, capsys):
        la_cli._stream_to_stdout(iter([{"text": "a"}, {"done": True, "code": 0}]), as_json=True)
        lines = [json.loads(line) for line in capsys.readouterr().out.strip().split("\n")]
        assert lines == [{"text": "a"}, {"done": True, "code": 0}]


class TestSiblingParams:
    def test_the_workspace_naming_convention_is_followed(self):
        assert la_cli._sibling_params("agents/momentum.mjs") == "agents/momentum.params.json"

    def test_a_file_with_no_extension_has_no_sibling(self):
        assert la_cli._sibling_params("momentum") == ""


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_wires_the_cli_and_captures_the_settings_reader(self):
        from unittest.mock import MagicMock

        import plugins.liveagents as plugin

        ctx = MagicMock()
        ctx.get_config = lambda key, default=None: default
        plugin.register(ctx)
        ctx.register_cli_command.assert_called_once()
        assert ctx.register_cli_command.call_args.kwargs["name"] == "liveagents"
        assert plugin.settings_reader() is ctx.get_config

    def test_the_cli_works_before_any_plugin_manager_has_run(self, monkeypatch):
        # A script or a test reaches the CLI directly; defaults are the right answer there.
        import plugins.liveagents as plugin

        monkeypatch.setattr(plugin, "_settings_getter", None)
        cfg = la_cli._config(_parse(["--token", "t", "agents"]))
        assert cfg.exchange_url == la_config.DEFAULT_EXCHANGE_URL
