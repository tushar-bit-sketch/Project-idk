import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dateutil import parser
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from src.fetcher import fetch_events_from_sources, load_sources_from_config
from src.generator import deduplicate_and_generate_items, generate_shift_summary
from src.models import ShiftHandoverReport
from src.publisher import publish_to_pdf, publish_to_slack_format

app = FastAPI(title="Shift Handover Generator Portal")

BASE_DIR = Path(__file__).resolve().parent

class GenerateRequest(BaseModel):
    shift_id: str
    start: str
    end: str
    prior_start: Optional[str] = None
    prior_end: Optional[str] = None
    config_file: Optional[str] = None
    tickets_file: str = "data/tickets.json"
    incidents_file: str = "data/incidents.json"
    chat_file: str = "data/chat_logs.json"

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "templates" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.post("/api/generate")
async def generate_handover(req: GenerateRequest):
    try:
        dt_start = parser.isoparse(req.start)
        dt_end = parser.isoparse(req.end)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {e}")

    if dt_start >= dt_end:
        raise HTTPException(status_code=400, detail="Shift start must be strictly before shift end.")

    if req.config_file and Path(req.config_file).exists():
        sources = load_sources_from_config(req.config_file)
    else:
        sources = [
            {"name": "ticketing", "path": req.tickets_file},
            {"name": "incident", "path": req.incidents_file},
            {"name": "chat", "path": req.chat_file}
        ]

    # Handle prior events for carry-forward tracking
    prior_events = None
    if req.prior_start and req.prior_end:
        try:
            p_start = parser.isoparse(req.prior_start)
            p_end = parser.isoparse(req.prior_end)
            prior_events, _ = fetch_events_from_sources(sources, p_start, p_end)
        except Exception as e:
            print(f"Warning: Failed to parse prior shift timestamps ({e})")

    events, unreachable = fetch_events_from_sources(sources, dt_start, dt_end)
    completed, in_progress, blockers, watch_list = deduplicate_and_generate_items(events, prior_events=prior_events)
    summary_text = generate_shift_summary(completed, in_progress, blockers, watch_list)

    tz_name = dt_start.tzname() or "UTC"

    report = ShiftHandoverReport(
        shift_id=req.shift_id,
        shift_start=req.start,
        shift_end=req.end,
        timezone=tz_name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary_paragraph=summary_text,
        completed=completed,
        in_progress=in_progress,
        blockers=blockers,
        watch_list=watch_list,
        unreachable_sources=unreachable
    )

    pdf_filename = f"handover_{req.shift_id.lower().replace(' ', '_')}.pdf"
    pdf_path = str(BASE_DIR / pdf_filename)
    publish_to_pdf(report, pdf_path)

    slack_filename = f"slack_{req.shift_id.lower().replace(' ', '_')}.txt"
    slack_path = str(BASE_DIR / slack_filename)
    slack_text = publish_to_slack_format(report, slack_path)

    return {
        "status": "success",
        "report": report.dict(),
        "pdf_path": pdf_path,
        "slack_text": slack_text
    }

@app.get("/api/download-pdf")
async def download_pdf(path: str):
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="PDF document not found")
    return FileResponse(path=str(p), filename=p.name, media_type="application/pdf")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)