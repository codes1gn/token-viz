# token-viz — Product Requirements Document

## 1. Problem Statement

AI coding agents (GitHub Copilot CLI, Cursor) consume tokens in ways that are opaque to users:
- You don't know which parts of your workflow cost the most
- Skills injected into system context silently inflate costs
- Subagents spin up and consume thousands of tokens without attribution
- There is no way to compare cost across sessions or optimize spending

`token-viz` solves this by parsing the agent session `events.jsonl` logs that Copilot and Cursor emit, reconstructing a token cost ledger, and generating an interactive offline HTML report with clear dashboards.

## 2. Goals

| ID | Goal |
|----|------|
| G1 | Parse `events.jsonl` files produced by GitHub Copilot CLI and Cursor |
| G2 | Report exact output tokens per turn (from `assistant.message.outputTokens`) |
| G3 | Report context breakdown: system / conversation / tools (from `session.compaction_start`) |
| G4 | Attribute tokens to subagents (time-bounded from `subagent.started` to `subagent.completed`) |
| G5 | Attribute tokens to skills (estimate from `skill.invoked.content` length) |
| G6 | Attribute tokens to tool calls (from `tool.execution_complete.result.content` length) |
| G7 | Show cost in USD using configurable per-model pricing table |
| G8 | Generate fully offline standalone HTML report with interactive dashboards |
| G9 | CLI `tv` with `analyze`, `report`, `cost`, `sessions` subcommands |
| G10 | SKILL.md for Cursor + GitHub Copilot agent integration |

## 3. Non-Goals

- Real-time streaming token counting (requires API intercept)
- Modifying or intercepting the agent runtime
- Cloud storage or remote dashboards

## 4. User Stories

**U1 — Session Cost Audit:** As a user, I want to run `tv report events.jsonl` and get an HTML report showing me exactly what this session cost and why.

**U2 — Top Cost Consumers:** I want to see which subagents, skills, and tools consumed the most tokens so I can optimize my workflow.

**U3 — Multi-Session Comparison:** I want to run `tv sessions ~/.copilot/session-state/` to compare token cost across all my sessions.

**U4 — Cost Estimation:** I want to query `tv cost events.jsonl --model claude-sonnet-4.6` to get a dollar amount for a session.

**U5 — Agent Integration:** I want to invoke `tv` from inside a Cursor or Copilot skill to get a cost summary mid-session.

## 5. Feature Specifications

### F1: Parser
- Reads `events.jsonl` line by line (streaming, low memory)
- Extracts: session metadata, model, turns, compaction snapshots, subagent spans, skill injections, tool calls
- Outputs a `SessionReport` data structure

### F2: Token Estimator
- For events with exact counts (`outputTokens`, `systemTokens`, `conversationTokens`, `toolDefinitionsTokens`): use exact value
- For content without exact counts: estimate via `len(text) // 4` (avg 4 chars/token)
- All estimates are clearly marked as `~` in the report

### F3: Pricing Engine
- Built-in pricing table (updatable via `~/.config/token-viz/pricing.json`)
- Models covered: claude-sonnet-4.6, claude-haiku-4.5, claude-opus-4, gpt-4o, gpt-4o-mini, gpt-4.1, gpt-5-mini
- Input / output price separate (output is typically 3–5× more expensive)
- Premium multiplier support (Copilot reports `billing.multiplier` in models.json)

### F4: Attribution Engine
- **Subagent spans**: Group all `assistant.message.outputTokens` between `subagent.started` and `subagent.completed` timestamps; attribute to agent name
- **Skills**: Estimate from `skill.invoked.data.content` length; each skill counted once per invocation
- **Tool calls**: Sum result content lengths from `tool.execution_complete.data.result.content`; group by tool name
- **System prompt**: From `compaction_start.data.systemTokens` (exact)
- **Tool definitions**: From `compaction_start.data.toolDefinitionsTokens` (exact)
- **User messages**: Estimate from user.message content lengths
- **Assistant output**: Sum all `assistant.message.outputTokens`

### F5: HTML Report Dashboards
Five tabs in the standalone HTML report:

| Tab | Dashboard |
|-----|-----------|
| Overview | Session summary cards: total tokens, cost, model, duration, turns, compactions |
| Context | Pie chart: system / conversation / tool-defs / overhead split |
| Timeline | Bar chart: output tokens per turn, colored by subagent/skill/tool |
| Components | Breakdown table + bar: subagents vs skills vs tools vs messages |
| Top | Ranked list: top 10 token consumers with cost in USD |

### F6: CLI
```
tv analyze <events.jsonl>                  # Print text summary
tv report <events.jsonl> [-o report.html]  # Generate HTML report
tv cost <events.jsonl> [--model X]         # Print cost breakdown
tv sessions [dir]                          # Scan dir for sessions, rank by cost
tv prices [--update]                       # Show / refresh pricing table
```

## 6. Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Language | Python 3.8+ | stdlib only, ships on all platforms |
| Parsing | `json`, streaming | low memory, handles 10MB+ logs |
| Estimation | char-count formula | no external deps |
| CLI | `argparse` | stdlib, no click/typer dependency |
| Report | Standalone HTML | inline CSS+JS+data, offline, single file |
| Charts | Vanilla JS + SVG | no D3/Chart.js, air-gap safe |
| Tests | `concurrent.futures` | parallel test harness |

## 7. Platform Support

| Platform | Support |
|----------|---------|
| GitHub Copilot CLI (VSCode) | Primary — events.jsonl at `~/.copilot/session-state/<id>/events.jsonl` |
| Cursor Editor | Planned — Cursor emits similar JSONL telemetry |
| Claude Code | Planned — similar telemetry structure |
| Manual JSONL | Any valid events.jsonl file |

## 8. Data Model

```
SessionReport
  session_id: str
  model: str
  start_time: str
  end_time: str
  turns: List[TurnReport]
  compaction_snapshots: List[CompactionSnapshot]
  subagent_spans: List[SubagentSpan]
  skill_invocations: List[SkillInvocation]
  tool_executions: List[ToolExecution]
  summary: TokenSummary

TurnReport
  turn_id: str
  start_ts: str
  end_ts: str
  output_tokens: int          # exact from outputTokens field
  tool_calls: List[str]       # tool names used
  is_subagent: bool
  subagent_name: str | None

CompactionSnapshot
  timestamp: str
  system_tokens: int          # exact
  conversation_tokens: int    # exact
  tool_defs_tokens: int       # exact
  pre_tokens: int             # exact (preCompactionTokens)

SubagentSpan
  agent_name: str
  tool_call_id: str
  start_ts: str
  end_ts: str
  output_tokens: int          # sum of turns within span

SkillInvocation
  name: str
  path: str
  content_len: int
  estimated_tokens: int       # content_len // 4

ToolExecution
  tool_name: str
  model: str
  result_len: int
  estimated_tokens: int       # result_len // 4

TokenSummary
  total_output_tokens: int    # exact
  total_input_estimate: int   # estimated
  system_tokens: int          # from last compaction
  conversation_tokens: int
  tool_defs_tokens: int
  skill_tokens: int           # estimated
  subagent_output_tokens: int # attributed to subagents
  main_agent_output_tokens: int
  cost_usd: float
```

## 9. Success Criteria

| Criterion | Target |
|-----------|--------|
| Parse events.jsonl without crash | 100% of well-formed files |
| Exact output tokens within 1% of real cost | 95% of turns |
| HTML report opens offline | Yes |
| All 5 dashboard tabs functional | Yes |
| Test harness ≥ 8,400 checks | ✓ |
| SKILL.md usable by Cursor/Copilot | Yes |
| Zero external dependencies | Yes |

## 10. CLI Design

```
$ tv analyze events.jsonl
Session: 0c96be6a  Model: claude-sonnet-4.6
Duration: 27h 30m  Turns: 881  Compactions: 21
───────────────────────────────────────────────
Output tokens  (exact):  1,247,330
Input estimate:         ~3,500,000
Total cost estimate:        ~$55.42
───────────────────────────────────────────────
By component:
  Subagents    (4):     142,000  tokens  $2.13
  Skills       (1):      ~4,200  tokens  ~$0.01
  Tools    (1,323):     ~82,000  tokens  ~$0.25
  Main agent:        1,019,130  tokens  $15.29
───────────────────────────────────────────────
Context (last snapshot):
  System:     8,823  tokens
  Conversation: 76,034  tokens
  Tool defs:  19,057  tokens
```
