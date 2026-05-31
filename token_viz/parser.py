"""Parse events.jsonl from Copilot CLI / Cursor agent sessions."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


def _est(text: str) -> int:
    """Estimate token count from text length (avg 4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class TurnReport:
    turn_id: str
    start_ts: str
    end_ts: str
    output_tokens: int
    output_exact: bool
    tool_calls: List[str] = field(default_factory=list)
    is_subagent: bool = False
    subagent_name: Optional[str] = None
    interaction_id: Optional[str] = None


@dataclass
class CompactionSnapshot:
    timestamp: str
    system_tokens: int
    conversation_tokens: int
    tool_defs_tokens: int
    pre_compaction_tokens: int = 0


@dataclass
class SubagentSpan:
    agent_name: str
    agent_display_name: str
    tool_call_id: str
    start_ts: str
    end_ts: str = ""
    output_tokens: int = 0
    turn_count: int = 0


@dataclass
class SkillInvocation:
    name: str
    path: str
    content_len: int
    estimated_tokens: int
    timestamp: str


@dataclass
class ToolExecution:
    tool_name: str
    model: str
    result_len: int
    estimated_tokens: int
    success: bool
    timestamp: str


@dataclass
class MessageRecord:
    role: str  # 'user', 'assistant', 'system'
    content_len: int
    estimated_tokens: int
    timestamp: str


@dataclass
class SessionReport:
    session_id: str
    model: str
    start_time: str
    end_time: str
    turns: List[TurnReport] = field(default_factory=list)
    compaction_snapshots: List[CompactionSnapshot] = field(default_factory=list)
    subagent_spans: List[SubagentSpan] = field(default_factory=list)
    skill_invocations: List[SkillInvocation] = field(default_factory=list)
    tool_executions: List[ToolExecution] = field(default_factory=list)
    messages: List[MessageRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def parse(path: str) -> SessionReport:
    """Parse events.jsonl file and return SessionReport."""
    report = SessionReport(
        session_id="",
        model="unknown",
        start_time="",
        end_time="",
    )

    # State for building spans / turns
    open_subagents: dict = {}  # tool_call_id -> SubagentSpan
    open_turns: dict = {}      # turn_id -> TurnReport (partial)
    last_open_turn_id: str = ""  # most recently turn_start'd (real events don't put turnId in messages)

    if not os.path.exists(path):
        report.warnings.append(f"File not found: {path}")
        return report

    with open(path, encoding="utf-8", errors="replace") as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError as e:
                report.warnings.append(f"Line {lineno}: JSON parse error: {e}")
                continue

            etype = evt.get("type", "")
            data = evt.get("data", {}) or {}
            ts = evt.get("timestamp", "")

            # ── Session metadata ───────────────────────────────────────
            if etype == "session.start":
                report.session_id = data.get("sessionId", "")
                report.model = data.get("selectedModel", "unknown")
                report.start_time = data.get("startTime", ts)

            elif etype == "session.shutdown":
                report.end_time = ts

            # ── Messages ───────────────────────────────────────────────
            elif etype == "system.message":
                content = data.get("content", "")
                report.messages.append(MessageRecord(
                    role="system",
                    content_len=len(content),
                    estimated_tokens=_est(content),
                    timestamp=ts,
                ))

            elif etype == "user.message":
                content = data.get("content", "")
                report.messages.append(MessageRecord(
                    role="user",
                    content_len=len(content),
                    estimated_tokens=_est(content),
                    timestamp=ts,
                ))

            # ── Turn lifecycle ──────────────────────────────────────────
            elif etype == "assistant.turn_start":
                tid = str(data.get("turnId", ""))
                iid = data.get("interactionId") or ""
                open_turns[tid] = TurnReport(
                    turn_id=tid,
                    start_ts=ts,
                    end_ts="",
                    output_tokens=0,
                    output_exact=False,
                    interaction_id=iid,
                )
                last_open_turn_id = tid

            elif etype == "assistant.message":
                # Real Copilot events don't embed turnId in assistant.message;
                # match by interactionId first, then fall back to last open turn.
                iid = data.get("interactionId") or ""
                msg_tid = str(data.get("turnId", ""))

                # Find the matching open turn
                matched_tid = None
                if msg_tid and msg_tid in open_turns:
                    matched_tid = msg_tid
                elif iid:
                    # Find the most recently opened turn with this interactionId
                    for candidate_tid, candidate_t in reversed(list(open_turns.items())):
                        if candidate_t.interaction_id == iid:
                            matched_tid = candidate_tid
                            break
                if matched_tid is None and last_open_turn_id and last_open_turn_id in open_turns:
                    matched_tid = last_open_turn_id

                # Extract tool call names
                tool_reqs = data.get("toolRequests", []) or []
                tool_names = [t.get("name", "") for t in tool_reqs if t.get("name")]

                output_tokens = data.get("outputTokens")
                exact = output_tokens is not None
                if not exact:
                    content = data.get("content", "") or ""
                    output_tokens = _est(content)

                if matched_tid is not None:
                    t = open_turns[matched_tid]
                    t.output_tokens += (output_tokens or 0)
                    t.output_exact = t.output_exact or exact
                    t.tool_calls.extend(tool_names)
                else:
                    # Turn_start may have been missed; create orphan turn
                    orphan_tid = msg_tid or f"orphan_{ts}"
                    open_turns[orphan_tid] = TurnReport(
                        turn_id=orphan_tid,
                        start_ts=ts,
                        end_ts="",
                        output_tokens=output_tokens or 0,
                        output_exact=exact,
                        tool_calls=tool_names,
                        interaction_id=iid,
                    )

            elif etype == "assistant.turn_end":
                tid = str(data.get("turnId", ""))
                if tid in open_turns:
                    t = open_turns.pop(tid)
                    t.end_ts = ts
                    report.turns.append(t)
                    if last_open_turn_id == tid:
                        last_open_turn_id = ""

            # ── Compaction ────────────────────────────────────────────
            elif etype == "session.compaction_start":
                snap = CompactionSnapshot(
                    timestamp=ts,
                    system_tokens=data.get("systemTokens", 0),
                    conversation_tokens=data.get("conversationTokens", 0),
                    tool_defs_tokens=data.get("toolDefinitionsTokens", 0),
                )
                report.compaction_snapshots.append(snap)

            elif etype == "session.compaction_complete":
                pre = data.get("preCompactionTokens", 0)
                if report.compaction_snapshots:
                    report.compaction_snapshots[-1].pre_compaction_tokens = pre

            # ── Subagents ────────────────────────────────────────────
            elif etype == "subagent.started":
                tcid = data.get("toolCallId", "")
                span = SubagentSpan(
                    agent_name=data.get("agentName", "unknown"),
                    agent_display_name=data.get("agentDisplayName", ""),
                    tool_call_id=tcid,
                    start_ts=ts,
                )
                open_subagents[tcid] = span

            elif etype == "subagent.completed":
                tcid = data.get("toolCallId", "")
                if tcid in open_subagents:
                    span = open_subagents.pop(tcid)
                    span.end_ts = ts
                    # Attribute turns that fall within this span's time range
                    for turn in report.turns:
                        if _ts_in_range(turn.start_ts, span.start_ts, span.end_ts):
                            span.output_tokens += turn.output_tokens
                            span.turn_count += 1
                            turn.is_subagent = True
                            turn.subagent_name = span.agent_name
                    report.subagent_spans.append(span)

            # ── Skills ───────────────────────────────────────────────
            elif etype == "skill.invoked":
                name = data.get("name", "unknown")
                content = data.get("content", "")
                path_val = data.get("path", "")
                report.skill_invocations.append(SkillInvocation(
                    name=name,
                    path=path_val,
                    content_len=len(content),
                    estimated_tokens=_est(content),
                    timestamp=ts,
                ))

            # ── Tools ───────────────────────────────────────────────
            elif etype == "tool.execution_complete":
                result = data.get("result", {}) or {}
                content = result.get("content", "") or ""
                detailed = result.get("detailedContent", "") or ""
                bigger = content if len(content) >= len(detailed) else detailed
                tool_name = _tool_name_from_call_id(data.get("toolCallId", ""), report)
                report.tool_executions.append(ToolExecution(
                    tool_name=tool_name,
                    model=data.get("model", report.model),
                    result_len=len(bigger),
                    estimated_tokens=_est(bigger),
                    success=data.get("success", True),
                    timestamp=ts,
                ))

    # Close any still-open turns (session ended mid-turn)
    for tid, t in open_turns.items():
        report.turns.append(t)

    # If no end_time, use last event timestamp
    if not report.end_time and report.turns:
        report.end_time = report.turns[-1].end_ts or report.turns[-1].start_ts

    return report


def _ts_in_range(ts: str, start: str, end: str) -> bool:
    """Check if timestamp ts is between start and end (string comparison works for ISO8601)."""
    if not ts or not start or not end:
        return False
    return start <= ts <= end


def _tool_name_from_call_id(call_id: str, report: SessionReport) -> str:
    """Try to find the tool name from recent turn tool_calls. Fallback: 'tool'."""
    for turn in reversed(report.turns[-20:]):
        if turn.tool_calls:
            return turn.tool_calls[-1]
    return "tool"
