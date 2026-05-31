# token-viz — AI Agent Skill

## Overview

`token-viz` (`tv`) parses GitHub Copilot CLI and Cursor `events.jsonl` session logs to produce interactive HTML reports showing token usage breakdown by component: subagents, skills, tools, system prompt, and main agent.

## Quick Start

```bash
# Analyze a session (text summary)
tv analyze ~/.copilot/session-state/<session-id>/events.jsonl

# Generate interactive HTML report
tv report ~/.copilot/session-state/<session-id>/events.jsonl -o report.html

# Show cost breakdown
tv cost events.jsonl --model claude-sonnet-4.6

# Rank all sessions by token cost
tv sessions ~/.copilot/session-state/

# Show pricing table
tv prices
```

## Commands

| Command | Description |
|---------|-------------|
| `tv analyze <file>` | Print text summary: tokens, cost, components, context |
| `tv report <file> [-o out.html]` | Generate 5-tab standalone HTML report |
| `tv cost <file> [--model X]` | Show cost breakdown with per-component attribution |
| `tv sessions [dir]` | Scan directory, rank sessions by token cost |
| `tv prices [--update]` | Show pricing table / reset to defaults |

## Session Log Location

**GitHub Copilot CLI (VSCode):**
```
~/.copilot/session-state/<session-id>/events.jsonl
```

**Finding the current session:**
```bash
# List all sessions sorted by most recent
ls -lt ~/.copilot/session-state/ | head -5
# Or use tv sessions to rank by cost
tv sessions
```

## Report Dashboards

The `tv report` command generates a single offline HTML file with 5 tabs:

| Tab | What It Shows |
|-----|---------------|
| **Overview** | Total tokens, cost, model, duration, subagents/skills |
| **Context** | Donut chart: System / Conversation / Tool Definitions split |
| **Timeline** | Bar chart: output tokens per turn (blue=main, orange=subagent) |
| **Components** | Ranked bars by category: subagents, skills, tools, system |
| **Top Consumers** | Top 10 items ranked by token count with USD cost |

## Token Attribution

| Source | Method | Exact? |
|--------|--------|--------|
| Main agent output | `assistant.message.outputTokens` | Yes |
| Subagent output | Sum of turns within subagent span | Yes |
| System prompt | `session.compaction_start.systemTokens` | Yes |
| Tool definitions | `session.compaction_start.toolDefinitionsTokens` | Yes |
| Skills | `skill.invoked.content` length ÷ 4 | Estimated |
| Tool results | `tool.execution_complete.result.content` length ÷ 4 | Estimated |

## Pricing Override

Create `~/.config/token-viz/pricing.json` to add custom pricing:
```json
{
  "my-custom-model": {"in": 2.50, "out": 10.00}
}
```
Units: USD per 1,000,000 tokens (MTok)

## Agent Integration Pattern

Agents can invoke `tv` at the end of a task to report token cost:

```bash
# Check cost of current session (Copilot CLI)
SESSION_DIR=$(ls -td ~/.copilot/session-state/*/ | head -1)
tv analyze "${SESSION_DIR}events.jsonl"
```

## Install

```bash
cd token-viz
pip install -e .
# or: python -m token_viz analyze events.jsonl
```
