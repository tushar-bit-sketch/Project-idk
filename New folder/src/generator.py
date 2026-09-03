from collections import defaultdict
from typing import List, Tuple, Optional
from .models import RawEvent, HandoverItem

def determine_section(event: RawEvent) -> str:
    status = event.status.lower()
    priority = (event.priority or "").upper()
    summary_lower = event.summary.lower()

    if any(k in status for k in ["resolved", "closed", "mitigated", "done"]):
        return "Completed"
    
    if any(k in status for k in ["escalated", "blocked"]) or (priority in ["P0", "P1", "CRITICAL"] and status not in ["resolved", "closed"]):
        return "Blockers"

    if any(k in status for k in ["watch", "monitoring", "flapping", "alert"]) or any(k in summary_lower for k in ["alert", "flapping", "memory leak", "spike", "intermittent", "high latency"]):
        return "Watch-list"

    return "In Progress"

def deduplicate_and_generate_items(
    events: List[RawEvent],
    prior_events: Optional[List[RawEvent]] = None
) -> Tuple[List[HandoverItem], List[HandoverItem], List[HandoverItem], List[HandoverItem]]:
    grouped = defaultdict(list)
    for ev in events:
        grouped[(ev.source, ev.record_id)].append(ev)

    # If prior events exist, find items that were active/unresolved in prior shift
    carried_forward_items: List[HandoverItem] = []
    if prior_events:
        prior_grouped = defaultdict(list)
        for pev in prior_events:
            prior_grouped[(pev.source, pev.record_id)].append(pev)
        
        for (p_src, p_rec_id), p_records in prior_grouped.items():
            # If touched in current shift, the current shift's event takes precedence
            if (p_src, p_rec_id) in grouped:
                continue

            p_records.sort(key=lambda x: x.timestamp)
            last_p_event = p_records[-1]
            p_sec = determine_section(last_p_event)

            # Only carry forward unresolved items (not Completed)
            if p_sec in ["Blockers", "In Progress", "Watch-list"]:
                cf_desc = f"{p_rec_id} [still open from previous shift | {last_p_event.status}]: {last_p_event.summary}"
                if last_p_event.owner:
                    cf_desc += f" (Owner: {last_p_event.owner})"
                if last_p_event.priority and last_p_event.priority in ["P0", "P1"]:
                    cf_desc += f" [Priority: {last_p_event.priority}]"

                cf_item = HandoverItem(
                    section=p_sec,
                    item=cf_desc,
                    source=f"{p_src}:{p_rec_id}",
                    timestamp=last_p_event.timestamp.isoformat(),
                    status_progression="still open from previous shift",
                    record_id=p_rec_id,
                    is_carried_forward=True
                )
                carried_forward_items.append(cf_item)

    completed: List[HandoverItem] = []
    in_progress: List[HandoverItem] = []
    blockers: List[HandoverItem] = []
    watch_list: List[HandoverItem] = []

    sorted_keys = sorted(grouped.keys(), key=lambda k: (k[0], k[1]))

    for (source_name, record_id) in sorted_keys:
        records = grouped[(source_name, record_id)]
        records.sort(key=lambda x: x.timestamp)

        first_status = records[0].status
        final_event = records[-1]
        final_status = final_event.status

        if len(records) > 1 and first_status != final_status:
            progression = f"{first_status} -> {final_status}"
            desc = f"{record_id} [{progression}]: {final_event.summary}"
        else:
            progression = final_status
            desc = f"{record_id} [{final_status}]: {final_event.summary}"

        if final_event.owner:
            desc += f" (Owner: {final_event.owner})"
        if final_event.priority and final_event.priority in ["P0", "P1"]:
            desc += f" [Priority: {final_event.priority}]"

        section = determine_section(final_event)
        grounded_source = f"{source_name}:{record_id}"

        item = HandoverItem(
            section=section,
            item=desc,
            source=grounded_source,
            timestamp=final_event.timestamp.isoformat(),
            status_progression=progression,
            record_id=record_id
        )

        if section == "Completed":
            completed.append(item)
        elif section == "Blockers":
            blockers.append(item)
        elif section == "Watch-list":
            watch_list.append(item)
        else:
            in_progress.append(item)

    # Append carried forward items deterministically
    for cf in sorted(carried_forward_items, key=lambda x: (x.source, x.record_id)):
        if cf.section == "Blockers":
            blockers.append(cf)
        elif cf.section == "Watch-list":
            watch_list.append(cf)
        elif cf.section == "In Progress":
            in_progress.append(cf)

    return completed, in_progress, blockers, watch_list

def generate_shift_summary(completed: List[HandoverItem], in_progress: List[HandoverItem], blockers: List[HandoverItem], watch_list: List[HandoverItem]) -> str:
    total_items = len(completed) + len(in_progress) + len(blockers) + len(watch_list)
    if total_items == 0:
        return "Shift concluded with no logged activity or tickets touched during the active window. All monitored systems operated normally."
    
    parts = []
    parts.append(f"Total {total_items} distinct item(s) processed during shift.")
    if blockers:
        parts.append(f"CRITICAL: {len(blockers)} active blocker(s) require immediate follow-up by incoming shift.")
    else:
        parts.append("No active blockers or unmitigated escalations.")
    
    parts.append(f"{len(completed)} item(s) resolved, {len(in_progress)} item(s) in progress, and {len(watch_list)} item(s) under observation.")
    return " ".join(parts)