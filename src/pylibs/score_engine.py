"""
Trust score calculation - Algorithm 3

Positive: s = s + alpha * (max - s)  
Negative: s = s * (1 - alpha)

Apply w times for weight w. This gives us:
- diminishing returns approaching max
- high scores drop harder on negatives  
- low scores recover faster on positives
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .models import Event, EventType, User


MIN_SCORE = 0.0
MAX_SCORE = 1000.0
DEFAULT_ALPHA = 0.25


@dataclass
class ScoreUpdate:
    prev: float
    new: float
    delta: float
    event: Event
    ts: datetime
    
    def to_dict(self):
        return {
            "previous_score": self.prev,
            "new_score": self.new,
            "delta": self.delta,
            "display_previous": round(self.prev),
            "display_new": round(self.new),
            "display_delta": round(self.delta),
            "event": self.event.to_dict(),
            "timestamp": self.ts.isoformat(),
        }


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _step_positive(s, alpha):
    # move toward max
    return s + alpha * (MAX_SCORE - s)


def _step_negative(s, alpha):
    # move toward 0
    return s * (1 - alpha)


def apply_event(score, event_type, weight, alpha=DEFAULT_ALPHA):
    """Apply event weight times, return new score."""
    for _ in range(weight):
        if event_type == EventType.POSITIVE:
            score = _step_positive(score, alpha)
        else:
            score = _step_negative(score, alpha)
    return _clamp(score, MIN_SCORE, MAX_SCORE)


class TrustScoreEngine:
    def __init__(self, alpha=None):
        self.alpha = alpha or DEFAULT_ALPHA
    
    def process(self, user: User, event: Event) -> ScoreUpdate:
        """Process event and update user score in place."""
        prev = user.score
        
        # weight 0 = no change (e.g. false alarm reports)
        if event.weight == 0:
            return ScoreUpdate(prev, prev, 0.0, event, datetime.utcnow())
        
        new = apply_event(prev, event.event_type, event.weight, user.alpha)
        user.score = new
        user.updated_at = datetime.utcnow()
        
        return ScoreUpdate(prev, new, new - prev, event, user.updated_at)
    
    def simulate(self, score, event_type, weight, alpha=None):
        """Preview what would happen without applying."""
        a = alpha or self.alpha
        new = apply_event(score, event_type, weight, a)
        return {
            "current": score,
            "simulated": new,
            "delta": new - score,
            "type": event_type.value,
            "weight": weight,
        }
    
    def events_to_target(self, current, target, event_type, alpha=None):
        """How many single-weight events to reach target? Returns -1 if unreachable."""
        a = alpha or self.alpha
        s = current
        
        # sanity check direction
        if event_type == EventType.POSITIVE and target <= current:
            return 0 if current >= target else -1
        if event_type == EventType.NEGATIVE and target >= current:
            return 0 if current <= target else -1
        
        for i in range(1, 1001):
            if event_type == EventType.POSITIVE:
                s = _step_positive(s, a)
                if s >= target:
                    return i
            else:
                s = _step_negative(s, a)
                if s <= target:
                    return i
        
        return -1
