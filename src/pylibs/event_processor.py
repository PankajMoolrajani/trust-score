"""
Event processing with dedup, frequency caps, etc.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .models import Event, EventCategory, EventSubtype, EventType, User
from .score_engine import ScoreUpdate, TrustScoreEngine


@dataclass
class FreqCap:
    max_count: int
    window: timedelta


@dataclass 
class ProcessResult:
    ok: bool
    update: Optional[ScoreUpdate] = None
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    
    def to_dict(self):
        return {
            "success": self.ok,
            "score_update": self.update.to_dict() if self.update else None,
            "error": self.error,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


# default caps - phishing reports are easy to game
DEFAULT_FREQ_CAPS = {
    EventSubtype.PHISH_REPORTED_VALID: FreqCap(2, timedelta(weeks=1)),
}


class EventProcessor:
    def __init__(self, engine=None, freq_caps=None):
        self.engine = engine or TrustScoreEngine()
        self.freq_caps = freq_caps or DEFAULT_FREQ_CAPS.copy()
        
        # in-memory for now, swap for db later
        self._events = {}  # dedup_key -> Event
        self._history = defaultdict(list)  # user_id -> [Event]
        self._users = {}
    
    def _check_freq(self, event):
        if event.subtype not in self.freq_caps:
            return True, None
        
        cap = self.freq_caps[event.subtype]
        hist = self._history.get(event.user_id, [])
        cutoff = datetime.utcnow() - cap.window
        
        cnt = sum(1 for e in hist if e.subtype == event.subtype and e.occurred_at >= cutoff)
        if cnt >= cap.max_count:
            return False, f"freq cap: {event.subtype.value} max {cap.max_count}/week"
        return True, None
    
    def _check_dedup(self, event):
        key = event.dedup_key
        if key in self._events:
            existing = self._events[key]
            return False, f"duplicate: already processed {existing.occurred_at.isoformat()}"
        return True, None
    
    def _validate(self, event):
        if not event.user_id:
            return False, "missing user_id"
        if not event.context.object_id:
            return False, "missing object_id"
        if event.weight < 0:
            return False, "negative weight"
        return True, None
    
    def get_user(self, user_id):
        return self._users.get(user_id)
    
    def get_or_create_user(self, user_id):
        if user_id not in self._users:
            self._users[user_id] = User(user_id=user_id)
        return self._users[user_id]
    
    def register_user(self, user):
        self._users[user.user_id] = user
    
    def process(self, event: Event) -> ProcessResult:
        # validate
        ok, err = self._validate(event)
        if not ok:
            return ProcessResult(ok=False, error=err)
        
        # dedup check
        ok, reason = self._check_dedup(event)
        if not ok:
            return ProcessResult(ok=True, skipped=True, skip_reason=reason)
        
        # freq cap
        ok, reason = self._check_freq(event)
        if not ok:
            return ProcessResult(ok=True, skipped=True, skip_reason=reason)
        
        user = self.get_or_create_user(event.user_id)
        update = self.engine.process(user, event)
        
        # record
        self._events[event.dedup_key] = event
        self._history[event.user_id].append(event)
        
        return ProcessResult(ok=True, update=update)
    
    def process_batch(self, events):
        return [self.process(e) for e in events]
    
    def get_history(self, user_id):
        return self._history.get(user_id, [])
    
    def clear_event(self, user_id, category, object_id):
        """Allow reprocessing - useful for status transitions."""
        key = f"{user_id}:{category.value}:{object_id}"
        if key in self._events:
            del self._events[key]
            return True
        return False
    
    def stats(self):
        return {
            "users": len(self._users),
            "events": len(self._events),
            "by_user": {uid: len(evts) for uid, evts in self._history.items()},
        }
