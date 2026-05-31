"""Token attribution and cost analysis for token-viz."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from token_viz.parser import SessionReport
from token_viz.pricing import load_pricing, estimate_cost, format_cost


@dataclass
class ComponentCost:
    name: str
    category: str  # 'subagent', 'skill', 'tool', 'system', 'conversation', 'main'
    tokens: int
    exact: bool
    cost_usd: float
    detail: str = ""


@dataclass
class ContextSnapshot:
    timestamp: str
    system_tokens: int
    conversation_tokens: int
    tool_defs_tokens: int
    pre_compaction_tokens: int
    total_tokens: int


@dataclass
class AnalysisResult:
    session_id: str
    model: str
    start_time: str
    end_time: str
    duration_seconds: float
    turn_count: int
    compaction_count: int
    subagent_count: int
    skill_count: int

    # Token counts
    total_output_tokens: int    # exact (sum of outputTokens)
    total_input_estimate: int   # estimated
    total_tokens_estimate: int

    # Cost
    total_cost_usd: float
    output_cost_usd: float
    input_cost_usd: float

    # Context breakdown (from latest compaction snapshot)
    system_tokens: int
    conversation_tokens: int
    tool_defs_tokens: int
    context_snapshots: List[ContextSnapshot]

    # Attributed components
    components: List[ComponentCost]

    # Turn timeline data
    turn_timeline: List[dict]   # {turn_id, output_tokens, ts, is_subagent, agent_name}

    # Top consumers
    top_consumers: List[ComponentCost]

    warnings: List[str] = field(default_factory=list)


def analyze(report: SessionReport, model_override: Optional[str] = None) -> AnalysisResult:
    """Analyze a SessionReport into a fully attributed AnalysisResult."""
    pricing = load_pricing()
    model = model_override or report.model

    # ── Duration ──────────────────────────────────────────────────────
    duration = _parse_duration(report.start_time, report.end_time)

    # ── Context snapshots ─────────────────────────────────────────────
    context_snapshots = []
    for snap in report.compaction_snapshots:
        total = snap.system_tokens + snap.conversation_tokens + snap.tool_defs_tokens
        context_snapshots.append(ContextSnapshot(
            timestamp=snap.timestamp,
            system_tokens=snap.system_tokens,
            conversation_tokens=snap.conversation_tokens,
            tool_defs_tokens=snap.tool_defs_tokens,
            pre_compaction_tokens=snap.pre_compaction_tokens,
            total_tokens=total,
        ))

    # ── Exact output tokens ───────────────────────────────────────────
    total_output_tokens = sum(t.output_tokens for t in report.turns)

    # ── Input token estimation ────────────────────────────────────────
    # Use compaction preCompactionTokens * count as total input proxy
    if report.compaction_snapshots:
        avg_pre = sum(s.pre_compaction_tokens for s in report.compaction_snapshots) / len(report.compaction_snapshots)
        n_compact = len(report.compaction_snapshots)
        total_input_estimate = int(avg_pre * n_compact)
    else:
        # Fallback: estimate from messages
        total_input_estimate = sum(m.estimated_tokens for m in report.messages)
        # Add system context size if available
        latest_snap = _latest_snapshot(report)
        if latest_snap:
            total_input_estimate += latest_snap.system_tokens + latest_snap.tool_defs_tokens

    total_tokens_estimate = total_input_estimate + total_output_tokens

    # ── Costs ─────────────────────────────────────────────────────────
    total_cost = estimate_cost(total_input_estimate, total_output_tokens, model, pricing)
    output_only_cost = estimate_cost(0, total_output_tokens, model, pricing)
    input_only_cost = estimate_cost(total_input_estimate, 0, model, pricing)

    # ── Component attribution ─────────────────────────────────────────
    components: List[ComponentCost] = []

    # System context (from latest snapshot)
    latest = _latest_snapshot(report)
    sys_tokens = latest.system_tokens if latest else 0
    tool_defs_tokens = latest.tool_defs_tokens if latest else 0
    conv_tokens = latest.conversation_tokens if latest else 0

    if sys_tokens > 0:
        components.append(ComponentCost(
            name="System Prompt",
            category="system",
            tokens=sys_tokens,
            exact=True,
            cost_usd=estimate_cost(sys_tokens, 0, model, pricing),
        ))
    if tool_defs_tokens > 0:
        components.append(ComponentCost(
            name="Tool Definitions",
            category="system",
            tokens=tool_defs_tokens,
            exact=True,
            cost_usd=estimate_cost(tool_defs_tokens, 0, model, pricing),
        ))

    # Skills
    skill_groups: Dict[str, ComponentCost] = {}
    for inv in report.skill_invocations:
        if inv.name not in skill_groups:
            skill_groups[inv.name] = ComponentCost(
                name=f"skill:{inv.name}",
                category="skill",
                tokens=0,
                exact=False,
                cost_usd=0.0,
                detail=inv.path,
            )
        skill_groups[inv.name].tokens += inv.estimated_tokens
        skill_groups[inv.name].cost_usd = estimate_cost(
            skill_groups[inv.name].tokens, 0, model, pricing)
    components.extend(skill_groups.values())

    # Subagents (exact output tokens)
    for span in report.subagent_spans:
        components.append(ComponentCost(
            name=f"subagent:{span.agent_name}",
            category="subagent",
            tokens=span.output_tokens,
            exact=True,
            cost_usd=estimate_cost(0, span.output_tokens, model, pricing),
            detail=f"{span.turn_count} turns",
        ))

    # Tools (estimated from result size, grouped by tool name)
    tool_groups: Dict[str, ComponentCost] = {}
    for te in report.tool_executions:
        key = te.tool_name
        if key not in tool_groups:
            tool_groups[key] = ComponentCost(
                name=f"tool:{key}",
                category="tool",
                tokens=0,
                exact=False,
                cost_usd=0.0,
            )
        tool_groups[key].tokens += te.estimated_tokens
    for comp in tool_groups.values():
        comp.cost_usd = estimate_cost(comp.tokens, 0, model, pricing)
    components.extend(tool_groups.values())

    # Main agent output (turns NOT attributed to subagents)
    main_output_tokens = sum(
        t.output_tokens for t in report.turns if not t.is_subagent
    )
    subagent_output_tokens = sum(
        t.output_tokens for t in report.turns if t.is_subagent
    )
    components.append(ComponentCost(
        name="Main Agent Output",
        category="main",
        tokens=main_output_tokens,
        exact=True,
        cost_usd=estimate_cost(0, main_output_tokens, model, pricing),
    ))

    # ── Turn timeline ────────────────────────────────────────────────
    turn_timeline = []
    for i, t in enumerate(report.turns):
        turn_timeline.append({
            "i": i,
            "turn_id": t.turn_id,
            "output_tokens": t.output_tokens,
            "ts": t.start_ts,
            "is_subagent": t.is_subagent,
            "agent_name": t.subagent_name or "",
            "tool_count": len(t.tool_calls),
            "exact": t.output_exact,
        })

    # ── Top consumers ─────────────────────────────────────────────────
    top = sorted(components, key=lambda c: c.tokens, reverse=True)[:10]

    # ── Latest context snapshot values ───────────────────────────────
    latest_snap = context_snapshots[-1] if context_snapshots else None

    return AnalysisResult(
        session_id=report.session_id,
        model=model,
        start_time=report.start_time,
        end_time=report.end_time,
        duration_seconds=duration,
        turn_count=len(report.turns),
        compaction_count=len(report.compaction_snapshots),
        subagent_count=len(report.subagent_spans),
        skill_count=len(set(inv.name for inv in report.skill_invocations)),
        total_output_tokens=total_output_tokens,
        total_input_estimate=total_input_estimate,
        total_tokens_estimate=total_tokens_estimate,
        total_cost_usd=total_cost,
        output_cost_usd=output_only_cost,
        input_cost_usd=input_only_cost,
        system_tokens=sys_tokens,
        conversation_tokens=conv_tokens,
        tool_defs_tokens=tool_defs_tokens,
        context_snapshots=context_snapshots,
        components=components,
        turn_timeline=turn_timeline,
        top_consumers=top,
        warnings=report.warnings,
    )


def _latest_snapshot(report: SessionReport):
    if report.compaction_snapshots:
        return report.compaction_snapshots[-1]
    return None


def _parse_duration(start: str, end: str) -> float:
    """Parse ISO8601 timestamps and return duration in seconds."""
    if not start or not end:
        return 0.0
    try:
        from datetime import datetime, timezone
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        # Handle both with and without milliseconds
        def parse_ts(s):
            for f in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(s[:26].replace("+08:00", "").rstrip("Z") + "Z", f)
                except ValueError:
                    continue
            return None
        t0 = parse_ts(start)
        t1 = parse_ts(end)
        if t0 and t1:
            return abs((t1 - t0).total_seconds())
    except Exception:
        pass
    return 0.0


def format_duration(seconds: float) -> str:
    """Format duration seconds as human-readable string."""
    if seconds <= 0:
        return "unknown"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def format_tokens(n: int, exact: bool = True) -> str:
    """Format token count with commas and exact/estimate marker."""
    prefix = "" if exact else "~"
    if n >= 1_000_000:
        return f"{prefix}{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{prefix}{n:,}"
    return f"{prefix}{n}"
