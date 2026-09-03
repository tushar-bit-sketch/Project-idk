import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Optional
from dateutil import parser
from .models import RawEvent

logger = logging.getLogger(__name__)

def parse_iso_timestamp(ts_str: str) -> datetime:
    dt = parser.isoparse(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt

def load_sources_from_config(config_path: str) -> List[dict]:
    """
    Stretch Goal 6: Packaged so another team can point it at their own
    data source with a config file and zero code changes.
    """
    cfg_file = Path(config_path).resolve()
    if not cfg_file.exists():
        logger.warning(f"Config file '{config_path}' not found.")
        return []
    try:
        with open(cfg_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict) and "sources" in data:
            return data["sources"]
        elif isinstance(data, list):
            return data
        else:
            logger.warning(f"Invalid config structure in '{config_path}'.")
            return []
    except Exception as e:
        logger.warning(f"Failed to parse config file '{config_path}': {e}")
        return []

def _fetch_live_api_events(
    cfg: dict,
    start_utc: datetime,
    end_utc: datetime
) -> Tuple[List[RawEvent], Optional[str]]:
    """
    Stretch Goal 5: Works against a real ticketing tool's live API.
    Reads token from environment variables (GITHUB_TOKEN or JIRA_API_TOKEN) - never hard-coded.
    Resilient to timeouts, bad tokens, or offline networks per Part 6.7.
    """
    source_name = cfg.get("name", "live_api")
    api_url = cfg.get("api_url")
    source_type = cfg.get("type", "rest_api")

    if not api_url:
        return [], f"{source_name} (missing api_url)"

    # Auth token from environment variable
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("JIRA_API_TOKEN") or os.environ.get("API_TOKEN")

    req = urllib.request.Request(api_url)
    req.add_header("User-Agent", "ShiftHandoverGenerator/1.0")
    req.add_header("Accept", "application/json")
    if token:
        if "github.com" in api_url or source_type == "github_issues":
            req.add_header("Authorization", f"Bearer {token}")
        else:
            req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status != 200:
                logger.warning(f"API {source_name} returned status {resp.status}")
                return [], source_name
            raw_data = resp.read().decode("utf-8")
            data = json.loads(raw_data)
    except Exception as e:
        logger.warning(f"Live API source '{source_name}' unreachable or failed: {e}. Skipping.")
        return [], source_name

    if not isinstance(data, list):
        if isinstance(data, dict) and "issues" in data:
            data = data["issues"]
        else:
            return [], source_name

    events = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rec_id = str(item.get("number") or item.get("id") or item.get("key") or "")
        if not rec_id:
            continue
        rec_id = f"GH-{rec_id}" if source_type == "github_issues" and not rec_id.startswith("GH-") else rec_id
        
        ts_val = item.get("updated_at") or item.get("created_at") or item.get("timestamp")
        if not ts_val:
            continue
        try:
            event_dt = parse_iso_timestamp(str(ts_val))
        except Exception:
            continue

        if start_utc <= event_dt < end_utc:
            status = str(item.get("state") or item.get("status") or "open").lower()
            summary = str(item.get("title") or item.get("summary") or "Untitled")
            
            # Extract priority from labels or fields if available
            labels = [l.get("name", "").upper() for l in item.get("labels", []) if isinstance(l, dict)]
            priority = "P0" if any("P0" in l or "CRITICAL" in l for l in labels) else "P3"

            events.append(RawEvent(
                source=source_name,
                record_id=rec_id,
                timestamp=event_dt,
                summary=summary,
                status=status,
                priority=priority,
                owner=item.get("user", {}).get("login") if isinstance(item.get("user"), dict) else None
            ))

    return events, None

def fetch_events_from_sources(
    source_configs: List[dict],
    shift_start: datetime,
    shift_end: datetime
) -> Tuple[List[RawEvent], List[str]]:
    valid_events: List[RawEvent] = []
    unreachable_or_failed_sources: List[str] = []

    start_utc = shift_start if shift_start.tzinfo else shift_start.replace(tzinfo=timezone.utc)
    start_utc = start_utc.astimezone(timezone.utc)
    
    end_utc = shift_end if shift_end.tzinfo else shift_end.replace(tzinfo=timezone.utc)
    end_utc = end_utc.astimezone(timezone.utc)

    for cfg in source_configs:
        source_name = cfg.get("name", "unknown")
        source_type = cfg.get("type")

        # Handle Live API Source
        if source_type in ["github_issues", "live_api", "rest_api"] or "api_url" in cfg:
            api_events, err_src = _fetch_live_api_events(cfg, start_utc, end_utc)
            if err_src:
                unreachable_or_failed_sources.append(err_src)
            valid_events.extend(api_events)
            continue

        filepath = cfg.get("path")
        
        if not filepath or not Path(filepath).exists():
            logger.warning(f"Source '{source_name}' at '{filepath}' is unreachable/missing. Skipping.")
            unreachable_or_failed_sources.append(source_name)
            continue
            
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Source '{source_name}' failed to parse JSON: {e}. Skipping.")
            unreachable_or_failed_sources.append(source_name)
            continue

        if not isinstance(data, list):
            logger.warning(f"Source '{source_name}' data format is not a list. Skipping.")
            unreachable_or_failed_sources.append(source_name)
            continue

        for idx, entry in enumerate(data):
            if not isinstance(entry, dict):
                logger.warning(f"Skipping malformed entry #{idx} in {source_name}: not an object.")
                continue

            record_id = entry.get("record_id")
            ts_val = entry.get("timestamp")
            summary = entry.get("summary")
            status = entry.get("status")

            if not record_id or not ts_val or not status or not summary:
                logger.warning(f"Skipping entry in {source_name} due to missing required fields: {entry}")
                continue

            try:
                event_dt = parse_iso_timestamp(str(ts_val))
            except Exception as e:
                logger.warning(f"Skipping entry {record_id} in {source_name} due to invalid timestamp '{ts_val}': {e}")
                continue

            if start_utc <= event_dt < end_utc:
                try:
                    event = RawEvent(
                        source=source_name,
                        record_id=str(record_id),
                        timestamp=event_dt,
                        summary=str(summary),
                        status=str(status).lower(),
                        priority=str(entry.get("priority", "P3")),
                        owner=entry.get("owner"),
                        details=entry.get("details")
                    )
                    valid_events.append(event)
                except Exception as e:
                    logger.warning(f"Skipping validation failure for record {record_id}: {e}")

    return valid_events, unreachable_or_failed_sources
