"""Contract tests for the LiveAgents trading skills.

The point of these skills is that somebody moving between Agent Terminal and this dashboard types
the same thing in both. So what is asserted is the contract, not the prose: that every Agent
Terminal command name exists here, that each one produces that exact slash command, that they call
subcommands the plugin actually has, and that the few safety statements which make the difference
between a demo and a funded mistake are present.

Nothing here reads for quality — that stays with review — and nothing freezes wording that is
expected to improve.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TRADING = REPO / "skills" / "trading"

# The command set Agent Terminal ships. A name missing here is a person typing a command that
# works in one place and not the other, which is the whole failure these skills exist to avoid.
AGENT_TERMINAL_COMMANDS = {
    "create-new-trading-agent",
    "create-new-news-agent",
    "create-new-rule-based-agent",
    "create-new-self-learning-agent",
    "backtest",
    "backtest-agent",
    "walk-forward",
    "optimise-agent",
    "deploy-agent-demo",
    "deploy-agent-live",
    "redeploy-agent",
    "start-agent",
    "stop-agent",
    "monitor-agent",
    "diagnose-agent",
}


def _skill_dirs():
    return sorted(p for p in TRADING.iterdir() if (p / "SKILL.md").is_file())


def _params():
    return [pytest.param(p, id=p.name) for p in _skill_dirs()]


def _read(path: Path):
    text = (path / "SKILL.md").read_text(encoding="utf-8")
    end = re.search(r"\n---\s*\n", text[3:])
    return yaml.safe_load(text[3 : end.start() + 3]), text


class TestCommandParity:
    def test_every_agent_terminal_command_exists_here(self):
        present = {p.name for p in _skill_dirs()}
        assert AGENT_TERMINAL_COMMANDS <= present, (
            f"missing: {sorted(AGENT_TERMINAL_COMMANDS - present)}")

    def test_the_hub_skill_is_present_too(self):
        # Where the platform reference lives, so the command skills can stay short.
        assert (TRADING / "liveagents" / "SKILL.md").is_file()

    @pytest.mark.parametrize("p", _params())
    def test_the_name_produces_the_slash_command_it_should(self, p):
        from agent.skill_commands import slugify_skill_name

        fm, _ = _read(p)
        # The slug is what a user types. A name that slugs to something else is a command nobody
        # can find.
        assert slugify_skill_name(fm["name"]) == p.name

    @pytest.mark.parametrize("p", _params())
    def test_no_name_collides_with_a_core_command(self, p):
        from hermes_cli.commands import resolve_command

        # A collision silently skips auto-registration, so the command would simply not exist.
        assert resolve_command(p.name) is None


class TestTheyCallCommandsThatExist:
    @pytest.mark.parametrize("p", _params())
    def test_referenced_subcommands_are_real(self, p):
        from plugins.liveagents import cli as la_cli

        _fm, text = _read(p)
        referenced = set(re.findall(r"hermes liveagents ([a-z][a-z-]*)", text))
        # `--json`-style flags and prose are excluded by the pattern; what is left must dispatch.
        unknown = referenced - set(la_cli._COMMANDS)
        assert not unknown, f"{p.name} calls subcommands that do not exist: {sorted(unknown)}"

    @pytest.mark.parametrize("p", _params())
    def test_referenced_sibling_commands_are_real(self, p):
        _fm, text = _read(p)
        present = {d.name for d in _skill_dirs()}
        referenced = set(re.findall(r"`/([a-z][a-z-]+)(?: |`)", text))
        # Only claims about this family are checked; a core command reference is somebody else's.
        dangling = {r for r in referenced if r in AGENT_TERMINAL_COMMANDS and r not in present}
        assert not dangling, f"{p.name} points at missing skills: {sorted(dangling)}"


class TestSafetyStatements:
    """The handful of facts that separate a demo from a funded mistake."""

    def test_a_live_deploy_warns_about_an_empty_sub_account(self):
        _fm, text = _read(TRADING / "deploy-agent-live")
        assert "no collateral" in text.lower() or "empty" in text.lower()
        # Retrying a live deploy on silence is the worst outcome this command has.
        assert "retry" in text.lower() or "again" in text.lower()

    def test_a_live_deploy_requires_both_credentials(self):
        _fm, text = _read(TRADING / "deploy-agent-live")
        assert "LIVEAGENTS_TERMINAL_TOKEN" in text
        assert "LIVEAGENTS_API_TOKEN" in text

    def test_stopping_says_it_does_not_close_positions(self):
        # The state people most often misread as safe. Emphasis markers are stripped first so the
        # assertion is about the statement, not about how it was marked up.
        _fm, text = _read(TRADING / "stop-agent")
        plain = text.lower().replace("*", "")
        assert "not close" in plain
        assert "exposed" in plain

    def test_demo_says_refused_orders_are_expected(self):
        _fm, text = _read(TRADING / "deploy-agent-demo")
        assert "refus" in text.lower()

    def test_diagnose_leads_with_the_commonest_cause(self):
        # A strategy that returns is treated as a crash, by a wide margin the usual reason.
        _fm, text = _read(TRADING / "diagnose-agent")
        assert "loop" in text.lower()

    def test_monitor_states_the_metric_caveats(self):
        _fm, text = _read(TRADING / "monitor-agent")
        lowered = text.lower()
        for caveat in ("realised", "heartbeat", "sharpe"):
            assert caveat in lowered, caveat

    def test_walk_forward_forbids_choosing_on_the_test_window(self):
        _fm, text = _read(TRADING / "walk-forward")
        assert "never sweep on the test window" in text.lower()

    def test_redeploy_says_the_sub_account_is_kept(self):
        _fm, text = _read(TRADING / "redeploy-agent")
        assert "sub-account" in text.lower()

    def test_the_short_backtest_name_defers_instead_of_duplicating(self):
        # Two copies of a procedure drift apart and then the two names do different things.
        _fm, text = _read(TRADING / "backtest")
        assert "backtest-agent" in text

    def test_the_hub_names_both_credentials_and_where_urls_live(self):
        _fm, text = _read(TRADING / "liveagents")
        assert "LIVEAGENTS_TERMINAL_TOKEN" in text
        assert "LIVEAGENTS_API_TOKEN" in text
        # URLs are behaviour, so they belong in config rather than in the environment.
        assert "plugins.entries.liveagents.settings" in text


class TestReferences:
    def test_the_hub_ships_the_shared_reference_it_points_at(self):
        refs = TRADING / "liveagents" / "references"
        _fm, text = _read(TRADING / "liveagents")
        for named in re.findall(r"`references/([a-z_]+\.md)`", text):
            assert (refs / named).is_file(), named
        # And it points at something, rather than duplicating the platform contract per command.
        assert list(refs.glob("*.md"))
