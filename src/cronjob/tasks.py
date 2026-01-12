"""
Scheduled tasks - deadline processing, cleanup, etc
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from src.pylibs import EventProcessor, TrustScoreEngine
from src.pylibs.models import Event, EventCategory, EventContext, EventSubtype, EventType

log = logging.getLogger(__name__)


class DeadlineChecker:
    """
    Tracks deadlines and generates events when they complete/expire.
    PENDING -> COMPLETED/LATE/OVERDUE (one final event per object)
    """
    
    def __init__(self, processor: EventProcessor):
        self.processor = processor
        self._deadlines = {}  # key -> deadline info
    
    def register(
        self,
        user_id: str,
        category: EventCategory,
        object_id: str,
        deadline_at: datetime,
        positive_st: EventSubtype,
        negative_st: EventSubtype,
        overdue_st: Optional[EventSubtype] = None,
        grace: timedelta = timedelta(days=7),
    ):
        key = f"{user_id}:{category.value}:{object_id}"
        self._deadlines[key] = {
            "user_id": user_id,
            "category": category,
            "object_id": object_id,
            "deadline": deadline_at,
            "positive": positive_st,
            "negative": negative_st,
            "overdue": overdue_st,
            "grace": grace,
            "status": "PENDING",
            "created": datetime.utcnow(),
        }
        log.info(f"deadline registered: {key} due {deadline_at}")
        return key
    
    def complete(self, user_id, category, object_id, completed_at):
        key = f"{user_id}:{category.value}:{object_id}"
        
        info = self._deadlines.get(key)
        if not info or info["status"] != "PENDING":
            return None
        
        on_time = completed_at <= info["deadline"]
        subtype = info["positive"] if on_time else info["negative"]
        
        event = Event(
            user_id=user_id,
            category=category,
            event_type=EventType.POSITIVE if on_time else EventType.NEGATIVE,
            context=EventContext(
                object_id=object_id,
                deadline_at=info["deadline"],
                completed_at=completed_at,
            ),
            subtype=subtype,
        )
        
        info["status"] = "COMPLETED" if on_time else "LATE"
        info["completed"] = completed_at
        
        log.info(f"deadline {key}: {subtype.value}")
        return event
    
    def check_overdue(self):
        """Run periodically to catch missed deadlines"""
        now = datetime.utcnow()
        events = []
        
        for key, info in list(self._deadlines.items()):
            if info["status"] != "PENDING":
                continue
            
            # past grace period?
            if info["overdue"] and now > info["deadline"] + info["grace"]:
                event = Event(
                    user_id=info["user_id"],
                    category=info["category"],
                    event_type=EventType.NEGATIVE,
                    context=EventContext(
                        object_id=info["object_id"],
                        deadline_at=info["deadline"],
                    ),
                    subtype=info["overdue"],
                )
                info["status"] = "OVERDUE"
                events.append(event)
                log.info(f"deadline overdue: {key}")
        
        return events
    
    def get_pending(self, user_id=None):
        return [
            {"key": k, **v}
            for k, v in self._deadlines.items()
            if v["status"] == "PENDING" and (not user_id or v["user_id"] == user_id)
        ]


class Tasks:
    def __init__(self, processor, deadline_checker=None):
        self.processor = processor
        self.deadlines = deadline_checker or DeadlineChecker(processor)
    
    def run_overdue_check(self):
        log.info("checking overdue deadlines...")
        events = self.deadlines.check_overdue()
        results = self.processor.process_batch(events)
        
        ok = sum(1 for r in results if r.ok and not r.skipped)
        log.info(f"overdue check done: {ok} processed")
        
        return {"task": "overdue", "processed": ok, "total": len(events)}
    
    def run_validation(self):
        """Make sure scores are in range"""
        log.info("validating scores...")
        issues = []
        
        for uid, user in self.processor._users.items():
            if user.score < 0 or user.score > 1000:
                issues.append({"user": uid, "score": user.score})
                user.score = max(0, min(1000, user.score))
        
        log.info(f"validation done: {len(issues)} issues")
        return {"task": "validation", "issues": len(issues)}
    
    def run_cleanup(self, days=90):
        """Remove old event history"""
        log.info(f"cleanup (>{days} days)...")
        cutoff = datetime.utcnow() - timedelta(days=days)
        removed = 0
        
        for uid in self.processor._history:
            before = len(self.processor._history[uid])
            self.processor._history[uid] = [
                e for e in self.processor._history[uid] if e.occurred_at >= cutoff
            ]
            removed += before - len(self.processor._history[uid])
        
        log.info(f"cleanup done: {removed} events removed")
        return {"task": "cleanup", "removed": removed}
    
    def run_daily_report(self):
        log.info("generating daily report...")
        
        dist = {"critical": 0, "low": 0, "medium": 0, "high": 0}
        for u in self.processor._users.values():
            if u.score < 200:
                dist["critical"] += 1
            elif u.score < 500:
                dist["low"] += 1
            elif u.score < 800:
                dist["medium"] += 1
            else:
                dist["high"] += 1
        
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent = sum(
            sum(1 for e in evts if e.occurred_at >= yesterday)
            for evts in self.processor._history.values()
        )
        
        return {
            "task": "report",
            "users": len(self.processor._users),
            "events_24h": recent,
            "distribution": dist,
        }


def create_tasks(processor):
    """Returns dict of task_name -> callable for scheduler integration"""
    t = Tasks(processor)
    return {
        "overdue": t.run_overdue_check,
        "validation": t.run_validation,
        "cleanup": t.run_cleanup,
        "report": t.run_daily_report,
    }
