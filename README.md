# Project-idk
# Shift Handover Note Generator (`shift-handover-generator`)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/badge/tests-5%20passed-brightgreen.svg)]()

An automated, grounded, and time-windowed shift handover documentation tool built for **IT HAPPENS @ RAALE #6**.

---

## 📌 Problem Overview
At shift handover, engineers, NOC operators, and on-call developers need to write a handover note summarizing:
- What was completed
- What remains in progress
- Blockers and escalations
- Watch-list items for the next shift

Doing this manually leads to missed context, dropped blockers, or vague summaries. 

This tool automates the process: it pulls raw operational activity from multiple sources (ticketing systems, incident logs, chat messages), strictly filters events to the active shift window $[start, end)$, collapses duplicate updates into a single state progression, and compiles an exportable single-file PDF document alongside a Slack summary.

---

## 🚀 Key Features

1. **Strict Shift-Window Boundary Enforcement**: Only events within $[shift\_start, shift\_end)$ are included. Backlog items not touched during the shift are never surfaced.
2. **Deterministic Grounding (Zero Hallucinations)**: Every bullet point cites its exact source (e.g. `ticketing:OPS-4821` or `incident:INC-889`). Nothing is invented.
3. **Mandatory Deduplication & State Progression**: Multi-stage updates to the same record collapse into a single line showing progression (e.g., `OPS-4821 [open -> escalated]: Login failures on mobile app`).
4. **Resilience to Hostile Input**: Missing files, corrupted JSON, and invalid timestamps are safely quarantined and logged without crashing the pipeline.
5. **Single-File Document Export**: Renders a clean PDF report via ReportLab, and writes `"Nothing to report"` for empty sections instead of omitting them.
6. **Multi-Format Output**: Simultaneously generates a single-page PDF and a Slack/Teams-ready Markdown/text snippet.

---

## 📂 Repository Structure

```text
shift-handover-generator/
├── data/                       # Test scenarios (quiet, busy, messy, hostile)
│   ├── tickets.json            # Mock ticket board data
│   ├── incidents.json          # Mock incident management logs
│   ├── chat_logs.json          # Mock ops/on-call chat channel
│   ├── quiet_tickets.json      # Minimal activity test data
│   ├── messy_tickets.json      # Out-of-order timestamps & duplicate updates
│   └── hostile_tickets.json    # Malformed timestamps & corrupted records
├── src/
│   ├── __init__.py
│   ├── models.py               # Pydantic schemas (RawEvent, HandoverItem, ShiftHandoverReport)
│   ├── fetcher.py              # Ingestion, UTC normalization & window boundary filtering
│   ├── generator.py            # Deduplication, progression tracker & section routing
│   └── publisher.py            # PDF document generator & Slack formatter
├── tests/
│   └── test_suite.py           # Comprehensive unit tests
├── main.py                     # CLI entrypoint
├── REPORT.md                   # Formal submission report (architecture, methods, test matrix)
├── README.md                   # Project overview and instructions
├── requirements.txt            # Python dependencies
└── .gitignore                  # Git exclusions (credentials, caches, virtualenvs)
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Clone the Repository
```bash
git clone https://github.com/<YOUR_USERNAME>/shift-handover-generator.git
cd shift-handover-generator
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 💻 Usage

### Generate a Shift Handover Note
Run `main.py` with your shift start and end times in ISO-8601 format:

```bash
python main.py \
  --start "2026-09-03T09:00:00+05:30" \
  --end "2026-09-03T17:00:00+05:30" \
  --shift-id "SHIFT-DAY-01" \
  --output-pdf "output_day01.pdf" \
  --output-slack "output_day01_slack.txt"
```

### Options & Arguments
- `--start`: *(Required)* Shift start timestamp (ISO-8601).
- `--end`: *(Required)* Shift end timestamp (ISO-8601).
- `--shift-id`: Unique identifier for the shift (Default: `SHIFT-DEFAULT`).
- `--output-pdf`: Target PDF file path (Default: `handover_note.pdf`).
- `--output-slack`: Optional plain-text / Slack formatted output.
- `--tickets-file`: Path to tickets JSON data source (Default: `data/tickets.json`).
- `--incidents-file`: Path to incidents JSON data source (Default: `data/incidents.json`).
- `--chat-file`: Path to chat JSON data source (Default: `data/chat_logs.json`).

---

## 🧪 Running Automated Tests

Run the full verification test suite:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

This verifies:
1. `test_window_filtering_strict_boundaries`: Confirms events outside the shift window are excluded.
2. `test_deduplication_and_state_progression`: Confirms repeated updates collapse to a single line.
3. `test_reproducibility_deterministic_output`: Confirms repeated runs produce identical outputs.
4. `test_quiet_shift_empty_sections`: Confirms empty categories display `"Nothing to report"`.
5. `test_hostile_corrupted_input_resilience`: Confirms malformed timestamps and corrupted JSON do not crash the app.

---

## 📄 Formal Report
For full technical documentation, architecture diagrams, sectioning rules, and the 6-shift verification matrix, please see [REPORT.md](REPORT.md).

---

## 👥 Contributors & Team
- **Tushar** ([@GitHubProfile](https://github.com/)) - Lead Developer
