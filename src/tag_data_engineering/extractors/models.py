import json
from typing import Any

from pydantic import BaseModel
from pydantic import Field


class ExtractionBatch(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)
    cursor: dict[str, str | int | bool | float | None] | None = None

    def to_json_lines(self) -> str:
        return "\n".join(json.dumps(record, default=str) for record in self.records)

    def estimated_size_bytes(self) -> int:
        return len(self.to_json_lines().encode("utf-8"))
