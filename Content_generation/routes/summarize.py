from fastapi import APIRouter, HTTPException
from typing import List
from models.schemas import SummarizeLinksRequest, LinkSummaryResponse
from utils.web_scrapping import extract_and_summarize_content

router = APIRouter()

@router.post("/summarize-links", response_model=List[LinkSummaryResponse])
def summarize_links(request: SummarizeLinksRequest):
    try:
        research_data = extract_and_summarize_content(request.links, request.topic)
        if not research_data:
            raise HTTPException(status_code=404, detail="No content could be summarized.")
        return research_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
