"""Lightweight SQLAlchemy Core tables for efficient bulk ingestion.

Only the append-heavy event tables are defined here (reads elsewhere use plain
SQL). Declaring them explicitly -- rather than reflecting -- keeps import cheap
and lets us use PostgreSQL's ON CONFLICT for idempotency + batched inserts.
"""

from sqlalchemy import (
    BigInteger,
    Column,
    MetaData,
    Numeric,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

metadata = MetaData()

exposures = Table(
    "exposures", metadata,
    Column("experiment_id", UUID(as_uuid=False)),
    Column("user_id", Text),
    Column("variant_key", Text),
    Column("exposed_at", TIMESTAMP(timezone=True)),
    Column("event_id", Text),
)

metric_events = Table(
    "metric_events", metadata,
    Column("id", BigInteger, primary_key=True),
    Column("project_id", UUID(as_uuid=False)),
    Column("user_id", Text),
    Column("metric_key", Text),
    Column("value", Numeric),
    Column("occurred_at", TIMESTAMP(timezone=True)),
    Column("event_id", Text),
)
