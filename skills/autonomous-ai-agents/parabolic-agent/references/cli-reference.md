# Parabolic CLI Reference

Live sources when anything looks stale: `parabolic --help`, `hermes <command> --help`,
https://hermes-agent.nousresearch.com/docs/reference/cli-commands

### Global Flags

```
hermes [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
parabolic chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
parabolic setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
parabolic model                Interactive model/provider picker
parabolic fallback [add|remove|list]  Fallback provider chain
parabolic config [show|edit|get|set|unset|path|env-path|check|migrate]
parabolic login / logout       OAuth sign-in / clear stored auth
parabolic doctor [--fix]       Check dependencies and config
parabolic status [--all]       Component status
```

### Tools & Skills

```
parabolic tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

parabolic skills list|browse|search QUERY|inspect ID
parabolic skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
parabolic skills config        Enable/disable skills per platform
parabolic skills check|update|uninstall|publish PATH
parabolic skills tap add REPO  Add a GitHub repo as a skill source
parabolic bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
parabolic mcp add NAME (--url or --command) | remove | list | test NAME
parabolic mcp catalog | install NAME     Curated catalog install
parabolic mcp configure NAME             Toggle tool selection
parabolic mcp serve                      Run Parabolic as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
parabolic gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `parabolic photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
parabolic sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
parabolic cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
parabolic webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
parabolic profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
parabolic profile rename A B | alias NAME | export NAME | import FILE
```

### Credentials & Pools

```
parabolic auth                 Interactive credential manager
parabolic auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
parabolic auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
parabolic desktop / gui        Native desktop app
parabolic dashboard            Web admin panel + embedded chat (--stop / --status)
parabolic proxy                OpenAI-compatible local proxy backed by an OAuth provider
parabolic portal               Quick setup / sign in via Nous Portal
parabolic kanban <verb>        Multi-agent work-queue board
parabolic project              Named multi-folder workspaces
parabolic skin list|use|set    Switch/tweak skins (see references/themes.md)
parabolic pets <verb>          Pet mascots (see references/petdex.md)
parabolic memory setup|status|off|reset   Memory provider
parabolic secrets bitwarden|onepassword   External secret stores
parabolic moa                  Mixture-of-Agents slots
parabolic hooks / security / backup / import / checkpoints / console
parabolic logs [-f] [errors]   View agent/error logs
parabolic send                 One-off message through a gateway platform
parabolic pairing / plugins / insights / journey / computer-use
parabolic acp                  ACP server (IDE integration)
parabolic completion bash|zsh|fish
parabolic update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `parabolic photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `parabolic config edit` · [Configuration docs](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `parabolic tools list` · [Tools reference](https://hermes-agent.nousresearch.com/docs/reference/tools-reference) |
| Skills catalog | `parabolic skills browse` · [Skills catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `parabolic model` · [Providers guide](https://hermes-agent.nousresearch.com/docs/integrations/providers) |
| Env variables | `parabolic config env-path` · [Env vars reference](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.hermes/logs/gateway.log` (or `parabolic logs`) |
| Sessions | `parabolic sessions browse` (reads state.db) |
