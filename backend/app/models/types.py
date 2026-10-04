import uuid

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONType = JSON().with_variant(JSONB(), "postgresql")


def new_id() -> str:
    return uuid.uuid4().hex
