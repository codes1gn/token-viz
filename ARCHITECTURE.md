# token-viz — Architecture

## Component Diagram

```
events.jsonl (Copilot/Cursor session log)
        │
        ▼
┌─────────────────────┐
│  parser.py          │  Line-by-line streaming JSON reader
│  parse_events()     │  → SessionReport dataclass
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  analyzer.py        │  Token attribution + cost calculation
│  analyze()          │  → AnalysisResult dataclass
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  renderer.py        │  Standalone HTML generation
│  render()           │  → report.html (all inline)
└─────────────────────┘
         
┌─────────────────────┐
│  pricing.py         │  Model pricing table + cost calculator
│  PRICING_TABLE      │  Built-in + ~/.config/token-viz/pricing.json
│  estimate_cost()    │
└─────────────────────┘

┌─────────────────────┐
│  cli.py             │  argparse CLI entry point
│  tv analyze         │  Text summary to stdout
│  tv report          │  HTML report generation
│  tv cost            │  Cost breakdown
│  tv sessions        │  Scan directory, rank by cost
│  tv prices          │  Show pricing table
└─────────────────────┘
```

## Data Flow

### 1. Parsing Phase

Input: `events.jsonl` (one JSON object per line)

Key events extracted:

| Event Type | Data Extracted | Use |
|------------|---------------|-----|
| `session.start` | sessionId, model, startTime | Session metadata |
| `system.message` | content | System prompt token estimation |
| `user.message` | content | User message token estimation |
| `assistant.message` | outputTokens, toolRequests | Exact output cost per turn |
| `assistant.turn_start` | turnId, timestamp, parentId | Turn timeline |
| `assistant.turn_end` | turnId, timestamp | Turn duration |
| `session.compaction_start` | systemTokens, conversationTokens, toolDefinitionsTokens | Context snapshot |
| `session.compaction_complete` | preCompactionTokens | Context size at compaction |
| `subagent.started` | toolCallId, agentName, parentId | Open subagent span |
| `subagent.completed` | toolCallId, agentName | Close subagent span |
| `skill.invoked` | name, content | Skill token estimation |
| `tool.execution_complete` | toolCallId, model, result.content | Tool result tokens |
| `session.shutdown` | timestamp | Session end time |

### 2. Attribution Phase

Token attribution follows this hierarchy:

```
Total Session Tokens
├── System Prompt            (compaction_start.systemTokens — exact)
├── Tool Definitions         (compaction_start.toolDefinitionsTokens — exact)
├── Skills                   (skill_invoked.content_len // 4 — estimate)
├── Subagents
│   ├── research-agent       (outputTokens sum within span — exact)
│   ├── task-agent           (outputTokens sum within span — exact)
│   └── explore-agent        (outputTokens sum within span — exact)
├── Tools (by name)
│   ├── powershell           (result content_len // 4 — estimate)
│   ├── view                 (result content_len // 4 — estimate)
│   └── grep                 (result content_len // 4 — estimate)
└── Main Agent               (outputTokens not in any subagent span — exact)
```

**Input token estimation strategy:**
- Use `preCompactionTokens` values: each compaction tells us the context window size at that moment
- Average compaction size × number of compactions ≈ total input consumed
- For cost: `total_estimated_input × input_price + total_output × output_price`

### 3. Rendering Phase

Single-file HTML with embedded JSON data:

```javascript
const REPORT_DATA = /*__REPORT_DATA__*/;
```

Five interactive tabs rendered from `REPORT_DATA`:

```
Tab 1: Overview
  ├── [card] Total Output Tokens (exact)
  ├── [card] Estimated Total Cost
  ├── [card] Model + Duration
  ├── [card] Turns / Compactions / Subagents
  └── [horizontal bar] Top 5 cost categories

Tab 2: Context
  ├── [donut chart] System / Conversation / Tool-Defs / Skills
  └── [table] Compaction history with timestamps

Tab 3: Timeline  
  ├── [bar chart] Output tokens per turn
  │   └── colored: blue=main, orange=subagent, green=tool-heavy
  └── [annotations] Subagent spans overlaid as brackets

Tab 4: Components
  ├── [horizontal bar] Subagents ranked by token cost
  ├── [horizontal bar] Tools ranked by result tokens
  ├── [horizontal bar] Skills ranked by injection size
  └── [summary table] all components with USD cost

Tab 5: Top Consumers
  └── [ranked list] Top 10 items by token cost with type badge
```

## Pricing Table Design

```python
PRICING_TABLE = {
    "claude-sonnet-4.6":  {"in": 3.00,  "out": 15.00},
    "claude-sonnet-4.5":  {"in": 3.00,  "out": 15.00},
    "claude-haiku-4.5":   {"in": 0.25,  "out": 1.25},
    "claude-opus-4":      {"in": 15.00, "out": 75.00},
    "gpt-4o":             {"in": 5.00,  "out": 15.00},
    "gpt-4o-mini":        {"in": 0.15,  "out": 0.60},
    "gpt-4.1":            {"in": 2.00,  "out": 8.00},
    "gpt-5-mini":         {"in": 0.40,  "out": 1.60},
    "gpt-5.4-mini":       {"in": 0.40,  "out": 1.60},
    # unit: USD per 1,000,000 tokens (MTok)
}
```

## Test Scenarios (15)

| ID | Scenario | Key Checks |
|----|----------|------------|
| T01 | Minimal session (session.start + 1 turn) | parses without crash, has model field |
| T02 | Session with outputTokens in assistant.message | exact token count extracted |
| T03 | Session with compaction_start event | systemTokens/conversationTokens/toolDefs extracted |
| T04 | Session with subagent.started + completed | subagent span created, agent name correct |
| T05 | Session with skill.invoked | skill tokens estimated, name correct |
| T06 | Session with tool.execution_complete | tool result tokens estimated |
| T07 | Session with multiple turns | turn count correct, output_tokens summed |
| T08 | Session with multiple compaction events | uses latest snapshot for breakdown |
| T09 | SKILL.md structure test | has Quick Start, tv commands, usage |
| T10 | Pricing table test | all 9 models present, in < out |
| T11 | Cost calculation test | cost = input*price_in + output*price_out |
| T12 | HTML report generation | single file, no external URLs |
| T13 | HTML contains all 5 tab names | Overview/Context/Timeline/Components/Top |
| T14 | Multi-subagent attribution | tokens attributed to correct agent name |
| T15 | Session with no compaction | graceful degradation, no crash |

Each scenario: 7 checks × 8 workers × 10 runs = 560 tasks per scenario
Total: 15 × 560 = **8,400 checks**

## Key Design Decisions

### D1: Exact vs Estimated Tokens
- `outputTokens` in `assistant.message` is EXACT (from model API response)
- All input token estimates use `len(text) // 4` with `~` prefix in UI
- Report clearly distinguishes exact vs estimated values

### D2: Subagent Attribution Method
- Subagent spans are delimited by `subagent.started.timestamp` and `subagent.completed.timestamp`
- Any `assistant.message.outputTokens` with `timestamp` in that range → attributed to that subagent
- Nested subagents (subagent calling another subagent) are resolved by innermost span

### D3: No External Dependencies
- Zero pip requirements for core functionality
- All HTML/CSS/JS is inline in renderer.py
- Pricing JSON from stdlib only

### D4: Graceful Degradation
- Missing compaction events → skip context breakdown tab (show N/A)
- Missing outputTokens → estimate from content length
- Unknown model in pricing table → use "unknown" cost with warning
- Malformed JSON line → skip with warning, continue parsing

### D5: Pricing Table Override
- If `~/.config/token-viz/pricing.json` exists, merge with built-in table
- Custom pricing takes precedence (allows enterprise pricing)
- `tv prices --update` reloads from built-in defaults

## File Structure

```
token-viz/
├── token_viz/
│   ├── __init__.py      (v1.0.0)
│   ├── __main__.py      (entry point)
│   ├── parser.py        (events.jsonl → SessionReport)
│   ├── analyzer.py      (SessionReport → AnalysisResult + costs)
│   ├── pricing.py       (PRICING_TABLE + estimate_cost)
│   ├── renderer.py      (AnalysisResult → standalone HTML)
│   └── cli.py           (argparse CLI: tv analyze/report/cost/sessions/prices)
├── tests/
│   ├── run_tests.py     (15-scenario harness, 8400 checks)
│   └── fixtures/
│       ├── minimal.jsonl        (T01: bare minimum session)
│       ├── with_tokens.jsonl    (T02: assistant.message with outputTokens)
│       ├── with_compaction.jsonl (T03: compaction snapshots)
│       ├── with_subagents.jsonl  (T04: subagent spans)
│       └── full_session.jsonl   (T06-T08: comprehensive fixture)
├── PRD.md
├── ARCHITECTURE.md
├── SKILL.md
├── README.md
├── docs/index.html
├── setup.py
├── requirements.txt
├── LICENSE
└── .github/workflows/
    ├── tests.yml
    └── pages.yml
```
