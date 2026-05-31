"""
token-viz test harness
15 scenarios x 7 checks x 8 workers x 10 runs = 8,400 total checks
"""
import sys
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from token_viz.parser import parse
from token_viz.analyzer import analyze, format_duration, format_tokens
from token_viz.pricing import PRICING_TABLE, get_prices, estimate_cost, load_pricing
from token_viz.renderer import render

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

def fix(name):
    return os.path.join(FIXTURES, name)


# ── Scenario definitions ─────────────────────────────────────────────────────
# Each scenario: (name, checks_fn)
# checks_fn receives nothing and returns list of (bool, str) tuples [(passed, description)]

def scenario_01():
    """T01: Minimal session parses without crash, has model field."""
    report = parse(fix("minimal.jsonl"))
    result = analyze(report)
    return [
        (report.session_id != "", "session_id is non-empty"),
        (report.model == "claude-sonnet-4.6", f"model correct (got {report.model!r})"),
        (len(report.turns) >= 1, f"at least 1 turn (got {len(report.turns)})"),
        (result.turn_count >= 1, "turn_count >= 1"),
        (result.total_output_tokens >= 0, "non-negative output tokens"),
        (not any("error" in w.lower() for w in report.warnings), "no critical warnings"),
        (result.model == "claude-sonnet-4.6", "result.model matches session"),
    ]


def scenario_02():
    """T02: Session with outputTokens in assistant.message — exact token extraction."""
    report = parse(fix("with_tokens.jsonl"))
    result = analyze(report)
    turns_with_tokens = [t for t in report.turns if t.output_exact]
    total_exact = sum(t.output_tokens for t in report.turns if t.output_exact)
    return [
        (len(turns_with_tokens) >= 2, f">=2 turns with exact tokens (got {len(turns_with_tokens)})"),
        (result.total_output_tokens == total_exact, f"total_output_tokens matches sum {total_exact}"),
        (total_exact == 160, f"sum of outputTokens=85+12+55+8=160 (got {total_exact})"),
        (result.model == "claude-haiku-4.5", f"model is claude-haiku-4.5 (got {result.model!r})"),
        (result.turn_count == 2, f"2 turns (got {result.turn_count})"),
        (len(report.tool_executions) >= 2, f">=2 tool executions (got {len(report.tool_executions)})"),
        (result.total_cost_usd >= 0, "cost is non-negative"),
    ]


def scenario_03():
    """T03: Session with compaction events — systemTokens extracted."""
    report = parse(fix("with_compaction.jsonl"))
    result = analyze(report)
    return [
        (len(report.compaction_snapshots) == 2, f"2 compaction snapshots (got {len(report.compaction_snapshots)})"),
        (result.compaction_count == 2, f"compaction_count=2 (got {result.compaction_count})"),
        (result.system_tokens == 9200, f"system_tokens=9200 (got {result.system_tokens})"),
        (result.tool_defs_tokens == 18500, f"tool_defs_tokens=18500 (got {result.tool_defs_tokens})"),
        (result.conversation_tokens == 70000, f"conversation_tokens=70000 (got {result.conversation_tokens})"),
        (report.compaction_snapshots[-1].pre_compaction_tokens == 100000, "pre_compaction_tokens=100000"),
        (result.total_input_estimate > 0, "input estimate > 0"),
    ]


def scenario_04():
    """T04: Session with subagents — span created, agent name correct."""
    report = parse(fix("with_subagents.jsonl"))
    result = analyze(report)
    agent_names = [s.agent_name for s in report.subagent_spans]
    subagent_output = sum(s.output_tokens for s in report.subagent_spans)
    return [
        (len(report.subagent_spans) == 2, f"2 subagent spans (got {len(report.subagent_spans)})"),
        ("research" in agent_names, f"'research' in spans {agent_names}"),
        ("explore" in agent_names, f"'explore' in spans {agent_names}"),
        (result.subagent_count == 2, f"subagent_count=2 (got {result.subagent_count})"),
        (subagent_output > 0, f"subagent tokens > 0 (got {subagent_output})"),
        (any(t.is_subagent for t in report.turns), "some turns marked as subagent"),
        (any(c.category == "subagent" for c in result.components), "subagent components present"),
    ]


def scenario_05():
    """T05: Session with skill.invoked — tokens estimated, name correct."""
    report = parse(fix("full_session.jsonl"))
    result = analyze(report)
    skill_names = [inv.name for inv in report.skill_invocations]
    skill_comps = [c for c in result.components if c.category == "skill"]
    return [
        (len(report.skill_invocations) >= 1, f">=1 skill invocation (got {len(report.skill_invocations)})"),
        ("durable-request" in skill_names, f"durable-request in skills {skill_names}"),
        (all(inv.estimated_tokens > 0 for inv in report.skill_invocations), "skill tokens > 0"),
        (len(skill_comps) >= 1, "skill component in result"),
        (skill_comps[0].exact == False, "skill tokens marked as estimate"),
        (skill_comps[0].tokens > 0, "skill component has tokens"),
        (skill_comps[0].category == "skill", "category is 'skill'"),
    ]


def scenario_06():
    """T06: Session with tool.execution_complete — result tokens estimated."""
    report = parse(fix("full_session.jsonl"))
    result = analyze(report)
    tool_execs = report.tool_executions
    tool_comps = [c for c in result.components if c.category == "tool"]
    return [
        (len(tool_execs) >= 3, f">=3 tool executions (got {len(tool_execs)})"),
        (all(te.estimated_tokens >= 0 for te in tool_execs), "all tool tokens >= 0"),
        (len(tool_comps) >= 1, "tool components present in result"),
        (all(c.exact == False for c in tool_comps), "tool tokens are estimates"),
        (sum(c.tokens for c in tool_comps) > 0, "total tool tokens > 0"),
        (all(te.model != "" for te in tool_execs), "all tool execs have model"),
        (any(te.tool_name in ["powershell", "view", "grep", "tool"] for te in tool_execs), "known tool names"),
    ]


def scenario_07():
    """T07: Multiple turns — turn count correct, output tokens summed."""
    report = parse(fix("with_tokens.jsonl"))
    result = analyze(report)
    return [
        (result.turn_count == 2, f"turn_count=2 (got {result.turn_count})"),
        (result.total_output_tokens == 160, f"total output tokens=160 (got {result.total_output_tokens})"),
        (len(result.turn_timeline) == 2, f"timeline has 2 entries (got {len(result.turn_timeline)})"),
        (result.turn_timeline[0]["output_tokens"] == 97, f"turn 0 = 85+12=97 (got {result.turn_timeline[0]['output_tokens']})"),
        (result.turn_timeline[1]["output_tokens"] == 63, f"turn 1 = 55+8=63 (got {result.turn_timeline[1]['output_tokens']})"),
        (all("i" in t for t in result.turn_timeline), "all timeline entries have 'i' field"),
        (all("ts" in t for t in result.turn_timeline), "all timeline entries have 'ts' field"),
    ]


def scenario_08():
    """T08: Multiple compaction events — latest snapshot used for breakdown."""
    report = parse(fix("with_compaction.jsonl"))
    result = analyze(report)
    # Latest compaction snapshot has systemTokens=9200 (second one)
    return [
        (len(result.context_snapshots) == 2, f"2 context snapshots (got {len(result.context_snapshots)})"),
        (result.system_tokens == 9200, f"uses latest: system_tokens=9200 (got {result.system_tokens})"),
        (result.context_snapshots[-1].system_tokens == 9200, "last snapshot has system_tokens=9200"),
        (result.context_snapshots[0].system_tokens == 9000, "first snapshot has system_tokens=9000"),
        (result.context_snapshots[-1].pre_compaction_tokens == 100000, "last pre_compaction=100000"),
        (result.context_snapshots[0].pre_compaction_tokens == 95000, "first pre_compaction=95000"),
        (result.total_input_estimate > 0, "input estimate positive"),
    ]


def scenario_09():
    """T09: SKILL.md structure test."""
    skill_path = os.path.join(ROOT, "SKILL.md")
    if not os.path.exists(skill_path):
        return [(False, "SKILL.md exists")] * 7
    content = open(skill_path, encoding="utf-8").read()
    return [
        (os.path.exists(skill_path), "SKILL.md exists"),
        ("## Quick Start" in content, "has ## Quick Start section"),
        ("tv " in content, "mentions tv command"),
        ("analyze" in content, "mentions analyze command"),
        ("report" in content, "mentions report command"),
        ("events.jsonl" in content, "mentions events.jsonl"),
        (len(content) > 500, f"SKILL.md has content (len={len(content)})"),
    ]


def scenario_10():
    """T10: Pricing table test — all key models present, in < out."""
    pricing = load_pricing()
    required = ["claude-sonnet-4.6", "claude-haiku-4.5", "gpt-4o", "gpt-4o-mini"]
    return [
        (len(pricing) >= 9, f">=9 models in pricing (got {len(pricing)})"),
        (all(m in pricing for m in required), f"required models present {[m for m in required if m not in pricing]}"),
        (all(pricing[m]["in"] < pricing[m]["out"] for m in pricing), "all models: in < out price"),
        (pricing["claude-sonnet-4.6"]["in"] == 3.00, "claude-sonnet-4.6 input price = $3"),
        (pricing["claude-sonnet-4.6"]["out"] == 15.00, "claude-sonnet-4.6 output price = $15"),
        (pricing["gpt-4o"]["in"] == 5.00, "gpt-4o input price = $5"),
        (get_prices("claude-sonnet-4.6-20250501", pricing) is not None, "prefix match works"),
    ]


def scenario_11():
    """T11: Cost calculation test — cost = input*price_in + output*price_out."""
    pricing = load_pricing()
    cost = estimate_cost(1_000_000, 1_000_000, "claude-sonnet-4.6", pricing)
    # $3 in + $15 out = $18
    return [
        (abs(cost - 18.0) < 0.001, f"1M in + 1M out = $18 for claude-sonnet-4.6 (got {cost})"),
        (estimate_cost(0, 0, "claude-sonnet-4.6", pricing) == 0.0, "zero tokens = $0"),
        (estimate_cost(0, 1_000_000, "claude-haiku-4.5", pricing) == 1.25, "1M out haiku = $1.25"),
        (estimate_cost(1_000_000, 0, "claude-haiku-4.5", pricing) == 0.25, "1M in haiku = $0.25"),
        (estimate_cost(0, 0, "unknown-model-xyz", pricing) == -1.0, "unknown model returns -1"),
        (estimate_cost(500_000, 200_000, "gpt-4o", pricing) > 0, "positive cost for gpt-4o"),
        (estimate_cost(1_000_000, 1_000_000, "gpt-4o", pricing) == 20.0, "gpt-4o: $5 in + $15 out = $20"),
    ]


def scenario_12():
    """T12: HTML report generation — single file, no external URLs."""
    report = parse(fix("full_session.jsonl"))
    result = analyze(report)
    html = render(result)
    return [
        (isinstance(html, str), "render returns string"),
        (len(html) > 5000, f"HTML is substantial (len={len(html)})"),
        ("<!DOCTYPE html>" in html, "has DOCTYPE"),
        ("cdn.jsdelivr" not in html and "cdnjs" not in html and "unpkg.com" not in html, "no external CDN"),
        ("const DATA = " in html, "has embedded DATA"),
        ("token-viz" in html.lower(), "mentions token-viz"),
        ("</html>" in html, "properly closed HTML"),
    ]


def scenario_13():
    """T13: HTML contains all 5 tab names."""
    report = parse(fix("with_subagents.jsonl"))
    result = analyze(report)
    html = render(result)
    return [
        ("Overview" in html, "Overview tab present"),
        ("Context" in html, "Context tab present"),
        ("Timeline" in html, "Timeline tab present"),
        ("Components" in html, "Components tab present"),
        ("Top" in html, "Top Consumers tab present"),
        ("showTab" in html, "tab switching JS present"),
        ("tab-overview" in html, "tab-overview element present"),
    ]


def scenario_14():
    """T14: Multi-subagent attribution — tokens attributed to correct agent."""
    report = parse(fix("with_subagents.jsonl"))
    result = analyze(report)
    research_span = next((s for s in report.subagent_spans if s.agent_name == "research"), None)
    explore_span = next((s for s in report.subagent_spans if s.agent_name == "explore"), None)
    research_comp = next((c for c in result.components if "research" in c.name), None)
    explore_comp = next((c for c in result.components if "explore" in c.name), None)
    return [
        (research_span is not None, "research span found"),
        (explore_span is not None, "explore span found"),
        (research_comp is not None, "research component in result"),
        (explore_comp is not None, "explore component in result"),
        (research_span is not None and research_span.output_tokens == 800, f"research span tokens=800 (turns 1+2: 300+500) got {research_span.output_tokens if research_span else 'None'}"),
        (explore_span is not None and explore_span.output_tokens == 420, f"explore span tokens=420 (turn 5) got {explore_span.output_tokens if explore_span else 'None'}"),
        (all(t.is_subagent for t in report.turns if t.turn_id in ["1", "2", "5"]), "turns 1,2,5 marked as subagent"),
    ]


def scenario_15():
    """T15: Session with no compaction — graceful degradation, no crash."""
    report = parse(fix("minimal.jsonl"))
    result = analyze(report)
    return [
        (len(report.compaction_snapshots) == 0, "no compaction snapshots"),
        (result.compaction_count == 0, "compaction_count=0"),
        (result.system_tokens == 0, "system_tokens=0 (no snapshot)"),
        (result.total_output_tokens >= 0, "non-negative output tokens"),
        (result.turn_count >= 1, "turn_count >= 1"),
        (isinstance(result.components, list), "components is list"),
        (not any("crash" in w.lower() or "exception" in w.lower() for w in result.warnings), "no crash warnings"),
    ]


SCENARIOS_ALL = [
    ("T01:minimal-parse",          scenario_01),
    ("T02:exact-output-tokens",    scenario_02),
    ("T03:compaction-context",     scenario_03),
    ("T04:subagent-spans",         scenario_04),
    ("T05:skill-invocation",       scenario_05),
    ("T06:tool-result-tokens",     scenario_06),
    ("T07:multi-turn-sum",         scenario_07),
    ("T08:multi-compaction",       scenario_08),
    ("T09:skill-md-structure",     scenario_09),
    ("T10:pricing-table",          scenario_10),
    ("T11:cost-calculation",       scenario_11),
    ("T12:html-generation",        scenario_12),
    ("T13:html-tabs",              scenario_13),
    ("T14:subagent-attribution",   scenario_14),
    ("T15:no-compaction-graceful", scenario_15),
]

assert len(SCENARIOS_ALL) == 15, f"Expected 15 scenarios, got {len(SCENARIOS_ALL)}"

N_CHECKS = 7
N_WORKERS = 8
N_RUNS = 10
TOTAL = len(SCENARIOS_ALL) * N_CHECKS * N_WORKERS * N_RUNS


def run_scenario_task(scenario_fn):
    """Run one scenario and return (passed_count, failed_list)."""
    try:
        checks = scenario_fn()
    except Exception as e:
        return 0, [f"EXCEPTION: {e}"]
    passed = sum(1 for ok, _ in checks if ok)
    failed = [desc for ok, desc in checks if not ok]
    return passed, failed


def main():
    print(f"token-viz test harness")
    print(f"Scenarios: {len(SCENARIOS_ALL)}  Checks/scenario: {N_CHECKS}  Workers: {N_WORKERS}  Runs: {N_RUNS}")
    print(f"Total checks: {TOTAL}")
    print("-" * 60)

    t0 = time.time()
    total_passed = 0
    total_failed = 0
    all_failures = []

    for s_name, s_fn in SCENARIOS_ALL:
        tasks = [s_fn] * (N_WORKERS * N_RUNS)
        s_passed = 0
        s_failed = 0
        failures = []

        with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
            futs = [ex.submit(run_scenario_task, fn) for fn in tasks]
            for fut in as_completed(futs):
                p, f = fut.result()
                s_passed += p
                s_failed += N_CHECKS - p
                failures.extend(f)

        total_passed += s_passed
        total_failed += s_failed

        status = "PASS" if s_failed == 0 else "FAIL"
        print(f"  [{status}] {s_name:<35} {s_passed:>5}/{s_passed+s_failed}")
        if failures:
            unique_failures = list(dict.fromkeys(failures))[:3]
            for f in unique_failures:
                print(f"         FAIL: {f}")
            all_failures.extend(unique_failures)

    elapsed = time.time() - t0
    print("-" * 60)
    print(f"Result: {total_passed}/{total_passed + total_failed} checks passed in {elapsed:.1f}s")

    if total_failed == 0:
        print(f"ALL {TOTAL} CHECKS PASSED")
        return 0
    else:
        print(f"{total_failed} CHECKS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
