"""Share and collaboration models."""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


ShareRole = Literal["owner", "editor", "viewer"]


class Comment(BaseModel):
    comment_id: str
    author_id: str
    author_name: str
    item_ref: Optional[str] = None  # day/activity reference
    text: str
    created_at: str


class ChecklistItem(BaseModel):
    item_id: str
    text: str
    done: bool = False
    assigned_to: Optional[str] = None


class BudgetEntry(BaseModel):
    member_id: str
    member_name: str
    amount_inr: float


class ShareRequest(BaseModel):
    trip_id: str
    role: ShareRole = "viewer"
    invitee_email: Optional[str] = None


class ShareResponse(BaseModel):
    share_token: str
    share_url: str
    role: ShareRole


class CollabTrip(BaseModel):
    trip_id: str
    share_token: str
    owner_id: str
    members: list[dict] = Field(default_factory=list)  # [{id, name, role}]
    comments: list[Comment] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    budget_split: list[BudgetEntry] = Field(default_factory=list)
    last_updated: str = ""
