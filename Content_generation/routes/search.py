# routes/search.py
from fastapi import APIRouter, HTTPException
from typing import List
from models.schemas import SearchRequest, SearchResult
from utils.internet_search import search_topic

router = APIRouter()

@router.post("/search", response_model=List[SearchResult])
def search_content(request: SearchRequest):
    try:
        # Use our search functionality
        results = search_topic(request.topic, request.num_results)
        
        # If no results found, return empty list
        if not results:
            print("Search returned no results")
            return []
        
        return results
    except Exception as e:
        print(f"Error in search_content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

