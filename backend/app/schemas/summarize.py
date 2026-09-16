from pydantic import BaseModel
from typing import Literal


class SummaryRequest(BaseModel):
    text: str
    length: Literal["short", "medium", "long"] = "medium"
    format: Literal["paragraph", "bullets", "table"] = "paragraph"
    executive: bool = False


class SummaryResponse(BaseModel):
    summary: str


class KeyPointsResponse(BaseModel):
    key_points: list[str]


class SectionSummary(BaseModel):
    section_index: int
    summary: str


class HierarchicalSummaryResponse(BaseModel):
    final_summary: str
    section_summaries: list[SectionSummary]
    total_sections: int
