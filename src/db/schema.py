"""
SQLAlchemy models
"""

import os
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, Session, mapped_column,
    relationship, sessionmaker,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=500.0)
    alpha: Mapped[float] = mapped_column(Float, default=0.25)
    trust_level: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    events = relationship("Event", back_populates="user", cascade="all, delete-orphan")
    history = relationship("EventHistory", back_populates="user", cascade="all, delete-orphan")
    freq_caps = relationship("FreqCapRecord", back_populates="user", cascade="all, delete-orphan")
    deadlines = relationship("DeadlineRecord", back_populates="user", cascade="all, delete-orphan")
    
    @property
    def display_score(self):
        return round(self.score)
    
    def update_trust_level(self):
        if self.score >= 800:
            self.trust_level = "HIGH"
        elif self.score >= 500:
            self.trust_level = "MEDIUM"
        elif self.score >= 200:
            self.trust_level = "LOW"
        else:
            self.trust_level = "CRITICAL"
        return self.trust_level
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "score": self.score,
            "display_score": self.display_score,
            "trust_level": self.trust_level,
            "alpha": self.alpha,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Event(Base):
    """Processed events - enforces dedup by (user_id, category, object_id)"""
    __tablename__ = "events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid4()))
    
    user_pk: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    
    category: Mapped[str] = mapped_column(String(50))  # PATCHING, IR, etc
    event_type: Mapped[str] = mapped_column(String(20))  # POSITIVE/NEGATIVE
    subtype: Mapped[str] = mapped_column(String(50), nullable=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    
    object_id: Mapped[str] = mapped_column(String(255))
    deadline_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # score delta
    prev_score: Mapped[float] = mapped_column(Float)
    new_score: Mapped[float] = mapped_column(Float)
    delta: Mapped[float] = mapped_column(Float)
    
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="events")
    
    __table_args__ = (
        UniqueConstraint("user_id", "category", "object_id", name="uq_event_dedup"),
        Index("ix_event_user_cat", "user_id", "category"),
    )
    
    def to_dict(self):
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "category": self.category,
            "type": self.event_type,
            "subtype": self.subtype,
            "weight": self.weight,
            "object_id": self.object_id,
            "prev_score": self.prev_score,
            "new_score": self.new_score,
            "delta": self.delta,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
        }


class EventHistory(Base):
    """Full audit log - includes skipped events"""
    __tablename__ = "event_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    
    user_pk: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    
    category: Mapped[str] = mapped_column(String(50))
    event_type: Mapped[str] = mapped_column(String(20))
    subtype: Mapped[str] = mapped_column(String(50), nullable=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    object_id: Mapped[str] = mapped_column(String(255))
    
    processed: Mapped[bool] = mapped_column(Boolean, default=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_reason: Mapped[str] = mapped_column(Text, nullable=True)
    
    prev_score: Mapped[float] = mapped_column(Float, nullable=True)
    new_score: Mapped[float] = mapped_column(Float, nullable=True)
    delta: Mapped[float] = mapped_column(Float, nullable=True)
    
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    raw_payload: Mapped[str] = mapped_column(Text, nullable=True)  # for debugging
    
    user = relationship("User", back_populates="history")
    
    __table_args__ = (
        Index("ix_hist_user_time", "user_id", "occurred_at"),
    )


class FreqCapRecord(Base):
    """Tracks events for rate limiting"""
    __tablename__ = "freq_cap_records"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_pk: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    subtype: Mapped[str] = mapped_column(String(50))
    event_at: Mapped[datetime] = mapped_column(DateTime)
    
    user = relationship("User", back_populates="freq_caps")
    
    __table_args__ = (
        Index("ix_freq_user_sub_time", "user_id", "subtype", "event_at"),
    )


class DeadlineRecord(Base):
    """Pending deadlines for status-based scoring"""
    __tablename__ = "deadline_records"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_pk: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    
    category: Mapped[str] = mapped_column(String(50))
    object_id: Mapped[str] = mapped_column(String(255))
    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    grace_hours: Mapped[int] = mapped_column(Integer, default=168)  # 7 days
    
    positive_subtype: Mapped[str] = mapped_column(String(50))
    negative_subtype: Mapped[str] = mapped_column(String(50))
    overdue_subtype: Mapped[str] = mapped_column(String(50), nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING/COMPLETED/LATE/OVERDUE
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    result_event_id: Mapped[str] = mapped_column(String(36), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="deadlines")
    
    __table_args__ = (
        UniqueConstraint("user_id", "category", "object_id", name="uq_deadline"),
        Index("ix_deadline_status", "status"),
    )


# --- db helpers ---

_engine = None
_Session = None


def get_engine(url=None):
    global _engine
    if _engine is None:
        db_url = url or os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/trust_score")
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def get_session() -> Session:
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine())
    return _Session()


def init_db(url=None):
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    return engine


class DBSession:
    """Context manager for db sessions"""
    def __init__(self):
        self.session = None
    
    def __enter__(self):
        self.session = get_session()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type:
                self.session.rollback()
            else:
                self.session.commit()
            self.session.close()
