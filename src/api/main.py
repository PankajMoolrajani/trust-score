"""
Trust Score REST API
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.pylibs import EventProcessor, TrustScoreEngine
from src.pylibs.models import (
    Event, EventCategory, EventContext, EventSubtype, EventType, User,
)


# --- request/response models ---

class ContextIn(BaseModel):
    object_id: str
    deadline_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class EventIn(BaseModel):
    event_id: Optional[str] = None
    user_id: str
    category: EventCategory
    type: EventType
    weight: int = Field(1, ge=0, le=10)
    subtype: Optional[EventSubtype] = None
    occurred_at: Optional[datetime] = None
    context: ContextIn
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "jsmith",
                "category": "PATCHING",
                "type": "POSITIVE",
                "subtype": "PATCH_ON_TIME",
                "context": {"object_id": "srv01-2026-01"}
            }
        }
    }


class EventOut(BaseModel):
    success: bool
    message: str
    score_update: Optional[dict] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


class UserOut(BaseModel):
    user_id: str
    score: float
    display_score: int
    trust_level: str
    alpha: float
    created_at: datetime
    updated_at: datetime


class SimIn(BaseModel):
    current_score: float = Field(..., ge=0, le=1000)
    event_type: EventType
    weight: int = Field(1, ge=1, le=10)
    alpha: Optional[float] = Field(None, ge=0.01, le=1.0)


# --- app setup ---

processor: Optional[EventProcessor] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global processor
    processor = EventProcessor()
    yield


app = FastAPI(
    title="Trust Score API",
    version="1.0.0",
    lifespan=lifespan,
)


# --- routes ---

@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}


@app.post("/events", response_model=EventOut)
async def submit_event(req: EventIn):
    try:
        ctx = EventContext(
            object_id=req.context.object_id,
            deadline_at=req.context.deadline_at,
            completed_at=req.context.completed_at,
        )
        
        event = Event(
            user_id=req.user_id,
            category=req.category,
            event_type=req.type,
            weight=req.weight,
            context=ctx,
            subtype=req.subtype,
            occurred_at=req.occurred_at or datetime.utcnow(),
        )
        
        if req.event_id:
            event.event_id = UUID(req.event_id)
        
        result = processor.process(event)
        
        if not result.ok:
            raise HTTPException(400, result.error)
        
        return EventOut(
            success=True,
            message="ok" if not result.skipped else "skipped",
            score_update=result.update.to_dict() if result.update else None,
            skipped=result.skipped,
            skip_reason=result.skip_reason,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/events/batch", response_model=list[EventOut])
async def submit_batch(requests: list[EventIn]):
    out = []
    for req in requests:
        try:
            ctx = EventContext(
                object_id=req.context.object_id,
                deadline_at=req.context.deadline_at,
                completed_at=req.context.completed_at,
            )
            event = Event(
                user_id=req.user_id,
                category=req.category,
                event_type=req.type,
                weight=req.weight,
                context=ctx,
                subtype=req.subtype,
                occurred_at=req.occurred_at or datetime.utcnow(),
            )
            if req.event_id:
                event.event_id = UUID(req.event_id)
            
            r = processor.process(event)
            out.append(EventOut(
                success=r.ok,
                message="ok" if r.ok else r.error,
                score_update=r.update.to_dict() if r.update else None,
                skipped=r.skipped,
                skip_reason=r.skip_reason,
            ))
        except ValueError as e:
            out.append(EventOut(success=False, message=str(e)))
    return out


@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: str):
    user = processor.get_user(user_id)
    if not user:
        raise HTTPException(404, "user not found")
    return UserOut(**user.to_dict())


@app.post("/users/{user_id}", response_model=UserOut)
async def create_user(
    user_id: str,
    score: float = Query(500.0, ge=0, le=1000),
    alpha: float = Query(0.25, ge=0.01, le=1.0),
):
    if processor.get_user(user_id):
        raise HTTPException(409, "user exists")
    
    user = User(user_id=user_id, score=score, alpha=alpha)
    processor.register_user(user)
    return UserOut(**user.to_dict())


@app.get("/users/{user_id}/history")
async def get_history(user_id: str, limit: int = Query(50, ge=1, le=200)):
    user = processor.get_user(user_id)
    if not user:
        raise HTTPException(404, "user not found")
    
    events = processor.get_history(user_id)
    return {
        "user_id": user_id,
        "score": user.display_score,
        "events": [e.to_dict() for e in events[-limit:]],
        "total": len(events),
    }


@app.patch("/users/{user_id}/alpha", response_model=UserOut)
async def set_alpha(user_id: str, alpha: float = Query(..., ge=0.01, le=1.0)):
    user = processor.get_user(user_id)
    if not user:
        raise HTTPException(404, "user not found")
    
    user.alpha = alpha
    user.updated_at = datetime.utcnow()
    return UserOut(**user.to_dict())


@app.post("/simulate")
async def simulate(req: SimIn):
    engine = TrustScoreEngine()
    return engine.simulate(req.current_score, req.event_type, req.weight, req.alpha)


@app.get("/simulate/trajectory")
async def trajectory(
    start: float = Query(..., ge=0, le=1000),
    target: float = Query(..., ge=0, le=1000),
    event_type: EventType = Query(...),
    alpha: float = Query(0.25, ge=0.01, le=1.0),
):
    engine = TrustScoreEngine(alpha)
    n = engine.events_to_target(start, target, event_type, alpha)
    return {
        "start": start,
        "target": target,
        "type": event_type.value,
        "events_needed": n,
        "reachable": n >= 0,
    }


@app.get("/stats")
async def stats():
    return processor.stats()


@app.delete("/admin/events/{user_id}/{category}/{object_id}")
async def clear_event(user_id: str, category: EventCategory, object_id: str):
    if not processor.clear_event(user_id, category, object_id):
        raise HTTPException(404, "event not found")
    return {"message": "cleared"}


@app.get("/ref/categories")
async def categories():
    return [c.value for c in EventCategory]


@app.get("/ref/subtypes")
async def subtypes():
    from src.pylibs.models import EVENT_WEIGHTS
    return {
        st.value: {"type": t.value, "weight": w}
        for st, (t, w) in EVENT_WEIGHTS.items()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
