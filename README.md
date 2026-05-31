<div align="center">

# &#x1F4CA; token-viz

### Know exactly where your tokens go.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white&style=flat-square)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-8%2C400%20passing-brightgreen?style=flat-square)](./tests)
[![Zero deps](https://img.shields.io/badge/deps-zero-orange?style=flat-square)](./requirements.txt)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

[&#x1F310; Website](https://codes1gn.github.io/token-viz) &bull;
[&#x2753; Why](#the-problem) &bull;
[&#x1F680; Quick Start](#quick-start) &bull;
[&#x1F4CA; Dashboards](#report-dashboards) &bull;
[&#x1F4BB; Commands](#commands) &bull;
[&#x1F9EA; Tests](#testing)

</div>

---

## The Problem

You're running AI agents all day. Subagents spin up. Skills inject thousands of tokens silently. The bill grows. You have **no idea** which part of your workflow is most expensive.

```
Without token-viz:                     With token-viz:
──────────────────────────────         ──────────────────────────────────────────────
You: *runs copilot session*            $ tv sessions
Agent: *does a lot of stuff*             Session       Turns  Output-tok   Cost
You: *opens bill next month*             abc12345        881   1,247,330  $55.42  <-- 😱
You: "...where did all that go?"         def67890        124     342,100   $8.11

                                       $ tv cost abc12345/events.jsonl
                                         subagent   (4):  142,000 tok   $2.13
                                         skill      (1):    4,200 tok  ~$0.01
                                         tool   (1323):   82,000 tok  ~$0.25
                                         main       (1): 1,019,130 tok $15.29
```

`token-viz` reads the `events.jsonl` logs that Copilot CLI already emits — no API keys, no intercepting, just parsing what's already there.

---

## Quick Start

```bash
git clone https://github.com/codes1gn/token-viz
cd token-viz
pip install -e .

# Analyze a session (stdout summary)
tv analyze ~/.copilot/session-state/<session-id>/events.jsonl

# Interactive 5-tab HTML dashboard
tv report ~/.copilot/session-state/<session-id>/events.jsonl -o report.html

# Compare all sessions by cost
tv sessions
```

---

## &#x2B50; Attribution Engine

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

---

## Report Dashboards

Open `report.html` in any browser — no server, no internet required:

| Tab | Dashboard |
|-----|-----------|
| **Overview** | Token totals, estimated cost, model, duration, top 5 consumers |
| **Context** | Donut chart: System / Conversation / Tool Definitions breakdown |
| **Timeline** | Bar chart: output tokens per turn, colored by subagent vs main |
| **Components** | Ranked bars for subagents / skills / tools / system prompt |
| **Top Consumers** | Top 10 items with USD cost estimate |

---

## Commands

| Command | Description |
|---------|-------------|
| `tv analyze <file>` | Text summary to stdout |
| `tv report <file> [-o out.html]` | Generate 5-tab HTML report |
| `tv cost <file> [--model X]` | Cost breakdown per component |
| `tv sessions [dir]` | Rank all sessions by token cost |
| `tv prices [--update]` | Show / reset pricing table |

---

## Token Attribution

`token-viz` uses exact values where available and clearly marks estimates:

| Source | Exactness | From |
|--------|-----------|------|
| Per-turn output tokens | ✅ Exact | `assistant.message.outputTokens` |
| System prompt size | ✅ Exact | `session.compaction_start.systemTokens` |
| Tool definitions | ✅ Exact | `session.compaction_start.toolDefinitionsTokens` |
| Conversation history | ✅ Exact | `session.compaction_start.conversationTokens` |
| Skill injection | ~Estimated | `skill.invoked.content` length ÷ 4 |
| Tool results | ~Estimated | `tool.execution_complete.result.content` length ÷ 4 |

---

## vs. Other Tools

| Feature | token-viz | Copilot UI | LangSmith | OpenAI Playground |
|---------|:---------:|:----------:|:---------:|:-----------------:|
| Works offline | ✅ | ❌ | ❌ | ❌ |
| Zero external deps | ✅ | N/A | ❌ | N/A |
| Subagent attribution | ✅ | ❌ | ❌ | N/A |
| Skill token tracking | ✅ | ❌ | ❌ | N/A |
| Per-turn breakdown | ✅ | ❌ | ✅ | ❌ |
| Multi-session compare | ✅ | ❌ | ✅ | ❌ |
| Free | ✅ | ✅ | ❌ | ❌ |

---

## Pricing Table

Built-in pricing for 14 models (as of 2026). Override with `~/.config/token-viz/pricing.json`:

```json
{ "my-model": {"in": 2.50, "out": 10.00} }
```

Supported: `claude-sonnet-4.6`, `claude-haiku-4.5`, `claude-opus-4`, `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-5-mini`, and more.

---

## Testing

```bash
python tests/run_tests.py --workers 8 --runs 10
```

```
15 scenarios × 7 checks × 8 workers × 10 runs = 8,400 checks
Pass rate: 100.0% ✅
```

---

## Requirements

- Python 3.8+ · Zero runtime dependencies (stdlib only)

## For AI Agents

See [SKILL.md](SKILL.md) — agents can invoke `tv` to report token cost at task boundaries.

---

## License

MIT © [codes1gn](https://github.com/codes1gn)

---

<div align="center">
  <sub>8,400/8,400 checks passing &bull; zero dependencies &bull; GitHub Copilot + Cursor</sub>
</div>
