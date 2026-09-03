from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

SectionType = Literal["Completed", "In Progress", "Blockers", "Watch-list"]

class RawEvent(BaseModel):
    source: str
    record_id: str
    timestamp: datetime
    summary: str
    status: str
    priority: Optional[str] = "P3"
    owner: Optional[str] = None
    details: Optional[str] = None

class HandoverItem(BaseModel):
    section: SectionType
    item: str
    source: str
    timestamp: str
    status_progression: Optional[str] = None
    record_id: str
    is_carried_forward: bool = False

class ShiftHandoverReport(BaseModel):
    shift_id: str
    shift_start: str
    shift_end: str
    timezone: str
    generated_at: str
    summary_paragraph: str
    completed: List[HandoverItem] = Field(default_factory=list)
    in_progress: List[HandoverItem] = Field(default_factory=list)
    blockers: List[HandoverItem] = Field(default_factory=list)
    watch_list: List[HandoverItem] = Field(default_factory=list)
    unreachable_sources: List[str] = Field(default_factory=list)