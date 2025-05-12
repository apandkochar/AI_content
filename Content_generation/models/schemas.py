from pydantic import BaseModel
from typing import List, Optional
from typing import Union, Dict
from enum import Enum

class TitleRequest(BaseModel):
    topic: str

class NewTitleRequest(BaseModel):
    topic: str
    previous_result: str

class TitleResponse(BaseModel):
    topic: str
    generated_titles: List[str]
    new_titles: Optional[List[str]] = []

class SearchRequest(BaseModel):
    topic: str
    num_results: Optional[int] = 5
    additional_info: Optional[str] = ""

class SearchResult(BaseModel):
    title: str
    href: str
    quality_score: float
    similarity_score: Optional[float] = 0.0
    additional_info: Optional[str] = ""

class LinkSummaryResponse(BaseModel):
    title: str
    link: str
    summarized_text: str

class SummarizeLinksRequest(BaseModel):
    links: List[str]
    topic: str

class LayoutRequest(BaseModel):
    topic: str
    title: str
    summary: str
    content_type: str
    layout_generator: str
    url: Optional[str] = None  # For URL layout

class LayoutResponse(BaseModel):
    layout: str
    confirmed: bool

class LayoutConfirmationRequest(BaseModel):
    topic: str
    title: str
    summary: str
    layout: str
    confirmed: bool

class LayoutItem(BaseModel):
    type: str
    level: Optional[str] = None
    text: Optional[str] = None
    position: int

class ContentType(str, Enum):
    BLOG = "blog"
    USE_CASE = "use_case"
    CASE_STUDY = "case_study"

class ContentGenRequest(BaseModel):
    topic: str
    title: str
    research_info: str
    layout: List[LayoutItem]
    content_type: ContentType
    tone: str

class ContentGenResponse(BaseModel):
    generated_content: str

# 🔧 Refinement Models
class RefineRequest(BaseModel):
    generated_content: str
    use_layout_instructions: bool
    use_research_context: bool
    layout: Optional[str] = ""
    research_context: Optional[str] = ""
    additional_instructions: Optional[str] = ""
    tone: Optional[str] = "neutral"

class RefineResponse(BaseModel):
    refined_content: str