from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import Session, declarative_base

from domain.models import AnomalyResult

Base = declarative_base()


class LogRecord(Base):
    __tablename__ = "log_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    level = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    host = Column(String(128), nullable=True)
    service = Column(String(128), nullable=True)
    remote_addr = Column(String(64), nullable=True)
    remote_user = Column(String(128), nullable=True)
    method = Column(String(16), nullable=True)
    path = Column(Text, nullable=True)
    protocol = Column(String(16), nullable=True)
    status = Column(Integer, nullable=True)
    bytes_sent = Column(Integer, nullable=True)
    referrer = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_time = Column(Float, nullable=True)
    attributes = Column(JSON, nullable=True)
    anomaly_score = Column(Float, nullable=False)
    is_anomaly = Column(Boolean, default=False)
    model_version = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Storage:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, future=True)

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)

    def save_results(self, results: list[AnomalyResult]) -> None:
        with Session(self.engine) as session:
            for result in results:
                event = result.event
                record = LogRecord(
                    timestamp=event.timestamp,
                    level=event.level,
                    message=event.message,
                    host=event.host,
                    service=event.service,
                    remote_addr=event.remote_addr,
                    remote_user=event.remote_user,
                    method=event.method,
                    path=event.path,
                    protocol=event.protocol,
                    status=event.status,
                    bytes_sent=event.bytes_sent,
                    referrer=event.referrer,
                    user_agent=event.user_agent,
                    request_time=event.request_time,
                    attributes=event.attributes,
                    anomaly_score=result.score,
                    is_anomaly=result.is_anomaly,
                    model_version=result.model_version,
                )
                session.add(record)
            session.commit()

    def get_anomalies(self, limit: int = 50, min_score: float | None = None) -> list[dict]:
        with Session(self.engine) as session:
            stmt = (
                select(LogRecord)
                .where(LogRecord.is_anomaly.is_(True))
                .order_by(LogRecord.anomaly_score.desc())
            )
            if min_score is not None:
                stmt = stmt.where(LogRecord.anomaly_score >= min_score)
            stmt = stmt.limit(limit)
            records = session.execute(stmt).scalars().all()
        return [self._record_to_dict(record) for record in records]

    def metrics(self) -> dict[str, float | int | str | None]:
        with Session(self.engine) as session:
            total = session.execute(select(func.count(LogRecord.id))).scalar_one()
            anomalies = session.execute(
                select(func.count(LogRecord.id)).where(LogRecord.is_anomaly.is_(True))
            ).scalar_one()
            latest = session.execute(select(func.max(LogRecord.created_at))).scalar_one()
        return {
            "total_events": int(total),
            "anomalies": int(anomalies),
            "anomaly_rate": float(anomalies) / float(total) if total else 0.0,
            "last_ingest": latest.isoformat() if latest else None,
        }

    def _record_to_dict(self, record: LogRecord) -> dict:
        return {
            "id": record.id,
            "timestamp": record.timestamp.isoformat(),
            "level": record.level,
            "message": record.message,
            "host": record.host,
            "service": record.service,
            "remote_addr": record.remote_addr,
            "remote_user": record.remote_user,
            "method": record.method,
            "path": record.path,
            "protocol": record.protocol,
            "status": record.status,
            "bytes_sent": record.bytes_sent,
            "referrer": record.referrer,
            "user_agent": record.user_agent,
            "request_time": record.request_time,
            "attributes": record.attributes,
            "anomaly_score": record.anomaly_score,
            "model_version": record.model_version,
        }
