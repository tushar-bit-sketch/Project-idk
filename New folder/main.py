import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from dateutil import parser
from src.fetcher import fetch_events_from_sources
from src.generator import deduplicate_and_generate_items, generate_shift_summary
from src.models import ShiftHandoverReport
from src.publisher import publish_to_pdf, publish_to_slack_format

def parse_args():
    p = argparse.ArgumentParser(description="Deterministic Grounded Shift Handover Note Generator")
    p.add_argument("--start", required=True, help="Shift start timestamp (ISO-8601)")
    p.add_argument("--end", required=True, help="Shift end timestamp (ISO-8601)")
    p.add_argument("--shift-id", default="SHIFT-DEFAULT", help="Unique shift identifier")
    p.add_argument("--output-pdf", default="handover_note.pdf", help="Target PDF file path")
    p.add_argument("--output-slack", default=None, help="Target Slack/text summary path")
    p.add_argument("--config", default=None, help="Path to JSON configuration file")
    p.add_argument("--prior-start", default=None, help="Prior shift start timestamp for carry-forward tracking")
    p.add_argument("--prior-end", default=None, help="Prior shift end timestamp for carry-forward tracking")
    p.add_argument("--tickets-file", default="data/tickets.json", help="Path to tickets source")
    p.add_argument("--incidents-file", default="data/incidents.json", help="Path to incidents source")
    p.add_argument("--chat-file", default="data/chat_logs.json", help="Path to chat logs source")
    return p.parse_args()

def main():
    args = parse_args()

    try:
        dt_start = parser.isoparse(args.start)
        dt_end = parser.isoparse(args.end)
    except Exception as e:
        print(f"FATAL: Invalid start or end timestamp provided: {e}", file=sys.stderr)
        sys.exit(1)

    if dt_start >= dt_end:
        print("FATAL: Shift start must be strictly before shift end.", file=sys.stderr)
        sys.exit(1)

    out_pdf = args.output_pdf
    out_slack = args.output_slack

    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.exists():
            print(f"FATAL: Config file not found: {args.config}", file=sys.stderr)
            sys.exit(1)
        import json
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg_data = json.load(f)
        sources = cfg_data.get("sources", [])
        if args.output_pdf == "handover_note.pdf" and "output_pdf" in cfg_data:
            out_pdf = cfg_data["output_pdf"]
        if not out_slack and "output_slack" in cfg_data:
            out_slack = cfg_data["output_slack"]
    else:
        sources = [
            {"name": "ticketing", "path": args.tickets_file},
            {"name": "incident", "path": args.incidents_file},
            {"name": "chat", "path": args.chat_file}
        ]

    print(f"[*] Processing shift: {args.shift_id}")
    print(f"[*] Window: {args.start} -> {args.end}")

    # Optional carry-forward prior events
    prior_events = None
    if args.prior_start and args.prior_end:
        try:
            p_start = parser.isoparse(args.prior_start)
            p_end = parser.isoparse(args.prior_end)
            print(f"[*] Sourcing prior shift window for carry-forward: {args.prior_start} -> {args.prior_end}")
            prior_events, _ = fetch_events_from_sources(sources, p_start, p_end)
            print(f"[*] Found {len(prior_events)} prior shift events to evaluate for carry-forward.")
        except Exception as e:
            print(f"[!] Warning: Failed to parse prior shift timestamps ({e}), skipping carry-forward.", file=sys.stderr)

    events, unreachable = fetch_events_from_sources(sources, dt_start, dt_end)
    print(f"[*] Sourced {len(events)} valid events inside active window.")
    if unreachable:
        print(f"[!] Unreachable / degraded sources: {unreachable}")

    completed, in_progress, blockers, watch_list = deduplicate_and_generate_items(events, prior_events=prior_events)
    summary_text = generate_shift_summary(completed, in_progress, blockers, watch_list)

    tz_name = dt_start.tzname() or "UTC"

    report = ShiftHandoverReport(
        shift_id=args.shift_id,
        shift_start=args.start,
        shift_end=args.end,
        timezone=tz_name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary_paragraph=summary_text,
        completed=completed,
        in_progress=in_progress,
        blockers=blockers,
        watch_list=watch_list,
        unreachable_sources=unreachable
    )

    publish_to_pdf(report, out_pdf)

    if out_slack:
        publish_to_slack_format(report, out_slack)
        print(f"[*] Published Slack summary to: {out_slack}")

if __name__ == "__main__":
    main()