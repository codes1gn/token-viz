# token-viz

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/tests-8%2C400%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/deps-zero-orange" alt="Zero dependencies">
  <img src="https://img.shields.io/badge/output-standalone%20HTML-purple" alt="Standalone HTML">
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT">
</p>

<p align="center">
  <strong>Know exactly where your tokens go.</strong><br>
  Parse GitHub Copilot CLI / Cursor session logs and generate interactive cost dashboards — offline, zero-dependency.
</p>

---

## The Problem

You're running AI agents all day. Subagents spin up. Skills inject thousands of tokens silently. The bill grows. You have no idea which part of your workflow is most expensive.

`token-viz` fixes this by reading the `events.jsonl` session logs that Copilot CLI already emits — no API keys, no intercepting, just parsing what's already there.

## ★ Star Feature: Attribution Engine

The report breaks down tokens not just by turn but by **component**:

```
Session: abc12345  Model: claude-sonnet-4.6
Turns: 881  |  Compactions: 21  |  Subagents: 4
────────────────────────────────────────────────────
Output tokens  (exact):  1,247,330
Input estimate:         ~3,500,000
Total cost estimate:        ~$55.42
────────────────────────────────────────────────────
By component:
  subagent      (4):    142,000 tokens   $2.13
  skill         (1):     ~4,200 tokens  ~$0.01
  tool      (1,323):    ~82,000 tokens  ~$0.25
  main          (1):  1,019,130 tokens  $15.29
────────────────────────────────────────────────────
Context (latest snapshot):
  System:         8,823 tokens
  Conversation:  76,034 tokens
  Tool defs:     19,057 tokens
```

## Quick Start

```bash
# Install
pip install -e .

# Analyze a session
tv analyze ~/.copilot/session-state/<session-id>/events.jsonl

# Generate interactive HTML report
tv report ~/.copilot/session-state/<session-id>/events.jsonl -o report.html

# Compare all sessions by cost
tv sessions
```

## Report Dashboards

Open `report.html` in any browser — no server, no internet required:

| Tab | Dashboard |
|-----|-----------|
| **Overview** | Token totals, estimated cost, model, duration, top 5 consumers |
| **Context** | Donut chart: System / Conversation / Tool Definitions breakdown |
| **Timeline** | Bar chart: output tokens per turn, colored by subagent (orange) vs main (blue) |
| **Components** | Ranked bars for subagents / skills / tools / system prompt |
| **Top Consumers** | Ranked list of top 10 items with USD cost |

## Commands

| Command | Description |
|---------|-------------|
| `tv analyze <file>` | Text summary to stdout |
| `tv report <file> [-o out.html]` | Generate 5-tab HTML report |
| `tv cost <file> [--model X]` | Cost breakdown per component |
| `tv sessions [dir]` | Rank all sessions by token cost |
| `tv prices [--update]` | Show / reset pricing table |

## Token Attribution Details

`token-viz` uses exact values where available and clearly marks estimates:

| Source | Exactness | From |
|--------|-----------|------|
| Per-turn output tokens | ✅ **Exact** | `assistant.message.outputTokens` |
| System prompt size | ✅ **Exact** | `session.compaction_start.systemTokens` |
| Tool definitions | ✅ **Exact** | `session.compaction_start.toolDefinitionsTokens` |
| Conversation history | ✅ **Exact** | `session.compaction_start.conversationTokens` |
| Skill injection | ~Estimated | `skill.invoked.content` length ÷ 4 |
| Tool results | ~Estimated | `tool.execution_complete.result.content` length ÷ 4 |

## Pricing Table

Built-in pricing for 14 models (as of 2026). Override with `~/.config/token-viz/pricing.json`:

```json
{ "my-model": {"in": 2.50, "out": 10.00} }
```

Supported models include: `claude-sonnet-4.6`, `claude-haiku-4.5`, `claude-opus-4`, `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-5-mini`, and more.

```bash
tv prices   # show full table
```

## vs. Other Tools

| Feature | token-viz | Copilot UI | LangSmith | OpenAI Playground |
|---------|-----------|------------|-----------|-------------------|
| Works offline | ✅ | ❌ | ❌ | ❌ |
| Zero external deps | ✅ | N/A | ❌ | N/A |
| Subagent attribution | ✅ | ❌ | ❌ | N/A |
| Skill token tracking | ✅ | ❌ | ❌ | N/A |
| Per-turn breakdown | ✅ | ❌ | ✅ | ❌ |
| Multi-session compare | ✅ | ❌ | ✅ | ❌ |
| Free | ✅ | ✅ | ❌ | ❌ |

## Install

```bash
git clone https://github.com/codes1gn/token-viz
cd token-viz
pip install -e .
```

Or run without install:

```bash
python -m token_viz analyze path/to/events.jsonl
```

## Requirements

- Python 3.8+
- Zero runtime dependencies (stdlib only)

## SKILL.md

For AI agent integration, see [SKILL.md](SKILL.md). Agents can invoke `tv` to report token cost at task boundaries.

## License

MIT © codes1gn
