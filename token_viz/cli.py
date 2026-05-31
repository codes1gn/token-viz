"""CLI entry point for token-viz (tv command)."""
import argparse
import json
import os
import sys

from token_viz import __version__
from token_viz.parser import parse
from token_viz.analyzer import analyze, format_duration, format_tokens
from token_viz.pricing import load_pricing, format_cost, PRICING_TABLE
from token_viz.renderer import render


def cmd_analyze(args):
    """Print text summary of a session events.jsonl."""
    report = parse(args.file)
    model = args.model or report.model
    result = analyze(report, model_override=model)

    sep = "-" * 52

    print(f"Session: {result.session_id[:8] or 'unknown'}")
    print(f"Model:   {result.model}")
    print(f"Duration:{format_duration(result.duration_seconds)}")
    print(f"Turns:   {result.turn_count}  |  Compactions: {result.compaction_count}")
    print(f"Subagents: {result.subagent_count}  |  Skills: {result.skill_count}")
    print(sep)
    print(f"Output tokens  (exact): {result.total_output_tokens:>12,}")
    print(f"Input estimate:        ~{result.total_input_estimate:>12,}")
    print(f"Total estimate:        ~{result.total_tokens_estimate:>12,}")
    if result.total_cost_usd >= 0:
        print(f"Total cost estimate:    {format_cost(result.total_cost_usd):>12}")
    print(sep)
    print("By component:")
    by_cat = {}
    for c in result.components:
        by_cat.setdefault(c.category, []).append(c)
    cat_order = ["subagent", "skill", "tool", "system", "main"]
    for cat in cat_order:
        items = by_cat.get(cat, [])
        if not items:
            continue
        total_t = sum(i.tokens for i in items)
        total_c = sum(i.cost_usd for i in items if i.cost_usd >= 0)
        exact = all(i.exact for i in items)
        print(f"  {cat:<12} ({len(items):>3}): {format_tokens(total_t, exact):>12}  {format_cost(total_c):>10}")
    print(sep)
    if result.system_tokens:
        print("Context (latest snapshot):")
        print(f"  System:       {result.system_tokens:>8,}  tokens")
        print(f"  Conversation: {result.conversation_tokens:>8,}  tokens")
        print(f"  Tool defs:    {result.tool_defs_tokens:>8,}  tokens")
    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  ! {w}")


def cmd_report(args):
    """Generate standalone HTML report."""
    report = parse(args.file)
    model = args.model or report.model
    result = analyze(report, model_override=model)

    out = args.output or args.file.replace(".jsonl", ".html")
    render(result, output_path=out)
    print(f"Report written to: {out}")
    print(f"  Turns: {result.turn_count}  Output tokens: {result.total_output_tokens:,}  Est. cost: {format_cost(result.total_cost_usd)}")


def cmd_cost(args):
    """Print cost breakdown."""
    report = parse(args.file)
    model = args.model or report.model
    result = analyze(report, model_override=model)

    pricing = load_pricing()
    print(f"Model: {result.model}")
    if model in pricing:
        p = pricing[model]
        print(f"Pricing: ${p['in']}/MTok input, ${p['out']}/MTok output")
    print(f"Input  (~{result.total_input_estimate:,} tokens): {format_cost(result.input_cost_usd)}")
    print(f"Output ({result.total_output_tokens:,} tokens): {format_cost(result.output_cost_usd)}")
    print(f"Total estimate: {format_cost(result.total_cost_usd)}")
    print()
    print("Cost by component:")
    sorted_comps = sorted(result.components, key=lambda c: c.tokens, reverse=True)
    for c in sorted_comps[:15]:
        exact_marker = "" if c.exact else "~"
        print(f"  {c.name:<40} {exact_marker}{c.tokens:>10,}  {format_cost(c.cost_usd):>12}")


def cmd_sessions(args):
    """Scan directory for sessions and rank by token cost."""
    base = args.dir or os.path.expanduser("~/.copilot/session-state")
    if not os.path.exists(base):
        print(f"Directory not found: {base}")
        sys.exit(1)

    rows = []
    for root, dirs, files in os.walk(base):
        for fname in files:
            if fname == "events.jsonl":
                fpath = os.path.join(root, fname)
                try:
                    report = parse(fpath)
                    result = analyze(report)
                    rows.append({
                        "path": fpath,
                        "session_id": result.session_id[:8],
                        "model": result.model,
                        "turns": result.turn_count,
                        "output_tokens": result.total_output_tokens,
                        "cost": result.total_cost_usd,
                        "start": result.start_time[:10] if result.start_time else "",
                    })
                except Exception as e:
                    print(f"  ! {fpath}: {e}", file=sys.stderr)

    rows.sort(key=lambda r: r["output_tokens"], reverse=True)
    print(f"{'Session':<10} {'Date':<12} {'Model':<22} {'Turns':>6} {'Out Tokens':>12} {'Est. Cost':>12}")
    print("-" * 80)
    for r in rows:
        print(f"{r['session_id']:<10} {r['start']:<12} {r['model']:<22} {r['turns']:>6,} {r['output_tokens']:>12,} {format_cost(r['cost']):>12}")


def cmd_prices(args):
    """Show or reset pricing table."""
    if args.update:
        custom_path = os.path.expanduser("~/.config/token-viz/pricing.json")
        if os.path.exists(custom_path):
            os.remove(custom_path)
            print(f"Custom pricing removed. Using built-in defaults.")
        else:
            print("No custom pricing found. Already using built-in defaults.")

    pricing = load_pricing()
    print(f"{'Model':<28} {'Input ($/MTok)':>16} {'Output ($/MTok)':>16}")
    print("-" * 64)
    for model, prices in sorted(pricing.items()):
        print(f"{model:<28} {prices['in']:>16.2f} {prices['out']:>16.2f}")


def main():
    parser = argparse.ArgumentParser(
        prog="tv",
        description=f"token-viz v{__version__} — AI agent session token visualizer",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # analyze
    p_analyze = sub.add_parser("analyze", help="Print text summary")
    p_analyze.add_argument("file", help="Path to events.jsonl")
    p_analyze.add_argument("--model", help="Override model for pricing")
    p_analyze.set_defaults(func=cmd_analyze)

    # report
    p_report = sub.add_parser("report", help="Generate standalone HTML report")
    p_report.add_argument("file", help="Path to events.jsonl")
    p_report.add_argument("-o", "--output", help="Output HTML path")
    p_report.add_argument("--model", help="Override model for pricing")
    p_report.set_defaults(func=cmd_report)

    # cost
    p_cost = sub.add_parser("cost", help="Print cost breakdown")
    p_cost.add_argument("file", help="Path to events.jsonl")
    p_cost.add_argument("--model", help="Override model for pricing")
    p_cost.set_defaults(func=cmd_cost)

    # sessions
    p_sessions = sub.add_parser("sessions", help="Scan directory, rank sessions by cost")
    p_sessions.add_argument("dir", nargs="?", help="Directory to scan (default: ~/.copilot/session-state)")
    p_sessions.set_defaults(func=cmd_sessions)

    # prices
    p_prices = sub.add_parser("prices", help="Show pricing table")
    p_prices.add_argument("--update", action="store_true", help="Reset to built-in defaults")
    p_prices.set_defaults(func=cmd_prices)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
