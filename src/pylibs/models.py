"""
Data models for trust score system
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class EventCategory(str, Enum):
    PATCHING = "PATCHING"
    IR = "IR"
    TRAINING = "TRAINING"
    PHISH_REPORT = "PHISH_REPORT"


class EventType(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class EventSubtype(str, Enum):
    # patching
    PATCH_ON_TIME = "PATCH_ON_TIME"
    PATCH_LATE = "PATCH_LATE"
    PATCH_OVERDUE = "PATCH_OVERDUE"
    
    # IR
    IR_ON_TIME = "IR_ON_TIME"
    IR_LATE = "IR_LATE"
    IR_IGNORED = "IR_IGNORED"
    IR_ESCALATED = "IR_ESCALATED"
    
    # training
    TRAINING_ON_TIME = "TRAINING_ON_TIME"
    TRAINING_LATE = "TRAINING_LATE"
    TRAINING_NOT_DONE = "TRAINING_NOT_DONE"
    
    # phishing
    PHISH_REPORTED_VALID = "PHISH_REPORTED_VALID"
    PHISH_NOT_REPORTED_AND_CLICKED = "PHISH_NOT_REPORTED_AND_CLICKED"
    PHISH_REPORTED_FALSE_ALARM = "PHISH_REPORTED_FALSE_ALARM"


# weight mappings - (type, weight)
# these are the defaults from the spec, can be overridden per-tenant later
EVENT_WEIGHTS = {
    EventSubtype.PATCH_ON_TIME: (EventType.POSITIVE, 1),
    EventSubtype.PATCH_LATE: (EventType.NEGATIVE, 1),
    EventSubtype.PATCH_OVERDUE: (EventType.NEGATIVE, 2),
    
    EventSubtype.IR_ON_TIME: (EventType.POSITIVE, 2),
    EventSubtype.IR_LATE: (EventType.NEGATIVE, 2),
    EventSubtype.IR_IGNORED: (EventType.NEGATIVE, 3),
    EventSubtype.IR_ESCALATED: (EventType.NEGATIVE, 3),
    
    EventSubtype.TRAINING_ON_TIME: (EventType.POSITIVE, 1),
    EventSubtype.TRAINING_LATE: (EventType.NEGATIVE, 1),
    EventSubtype.TRAINING_NOT_DONE: (EventType.NEGATIVE, 2),
    
    EventSubtype.PHISH_REPORTED_VALID: (EventType.POSITIVE, 2),
    EventSubtype.PHISH_NOT_REPORTED_AND_CLICKED: (EventType.NEGATIVE, 2),
    EventSubtype.PHISH_REPORTED_FALSE_ALARM: (EventType.POSITIVE, 0),  # no impact
}


@dataclass
class EventContext:
    object_id: str  # ticket id, device id, campaign id, etc
    deadline_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self):
        return {
            "object_id": self.object_id,
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class Event:
    """
    One score-impacting event per object. Dedup by (user_id, category, object_id).
    """
    user_id: str
    category: EventCategory
    event_type: EventType
    context: EventContext
    weight: int = 1
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    subtype: Optional[EventSubtype] = None
    
    def __post_init__(self):
        # if subtype provided, use its predefined type/weight
        if self.subtype and self.subtype in EVENT_WEIGHTS:
            self.event_type, self.weight = EVENT_WEIGHTS[self.subtype]
    
    @property
    def dedup_key(self):
        return f"{self.user_id}:{self.category.value}:{self.context.object_id}"
    
    def to_dict(self):
        return {
            "event_id": str(self.event_id),
            "user_id": self.user_id,
            "category": self.category.value,
            "type": self.event_type.value,
            "weight": self.weight,
            "occurred_at": self.occurred_at.isoformat(),
            "subtype": self.subtype.value if self.subtype else None,
            "context": self.context.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        ctx = data.get("context", {})
        context = EventContext(
            object_id=ctx.get("object_id", ""),
            deadline_at=datetime.fromisoformat(ctx["deadline_at"]) if ctx.get("deadline_at") else None,
            completed_at=datetime.fromisoformat(ctx["completed_at"]) if ctx.get("completed_at") else None,
        )
        
        return cls(
            event_id=UUID(data["event_id"]) if data.get("event_id") else uuid4(),
            user_id=data["user_id"],
            category=EventCategory(data["category"]),
            event_type=EventType(data["type"]),
            weight=data.get("weight", 1),
            occurred_at=datetime.fromisoformat(data["occurred_at"]) if data.get("occurred_at") else datetime.utcnow(),
            context=context,
            subtype=EventSubtype(data["subtype"]) if data.get("subtype") else None,
        )


@dataclass
class User:
    user_id: str
    score: float = 500.0  # neutral start
    alpha: float = 0.25
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def display_score(self):
        return round(self.score)
    
    @property
    def trust_level(self):
        # TODO: make these thresholds configurable
        if self.score >= 800:
            return "HIGH"
        elif self.score >= 500:
            return "MEDIUM"
        elif self.score >= 200:
            return "LOW"
        return "CRITICAL"
    
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "score": self.score,
            "display_score": self.display_score,
            "trust_level": self.trust_level,
            "alpha": self.alpha,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
