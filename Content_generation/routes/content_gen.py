from fastapi import APIRouter, HTTPException
from utils.input_layout import LayoutExtractor
from utils.content_generation import generate_content
from models.schemas import ContentGenRequest, ContentGenResponse

router = APIRouter()
le = LayoutExtractor()

@router.post("/generate-content", response_model=ContentGenResponse)
def generate_final_content(payload: ContentGenRequest):
    try:
        content = generate_content(
            topic=payload.topic,
            title=payload.title,
            research_info=payload.research_info,
            layout=[item.dict() for item in payload.layout],
            content_type=payload.content_type,
            tone=payload.tone
        )
        if not content:
            raise HTTPException(status_code=500, detail="Content generation failed.")
        
        return ContentGenResponse(generated_content=content)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
