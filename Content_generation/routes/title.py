from fastapi import APIRouter, HTTPException
from models.schemas import TitleRequest, NewTitleRequest, TitleResponse
from utils.title_generator import title_generate, generate_new_titles, save_results, load_all_titles

router = APIRouter()

@router.post("/generate-titles", response_model=TitleResponse)
def generate_titles(data: TitleRequest):
    try:
        raw_result = title_generate(data.topic)
        titles = [t.strip() for t in raw_result.splitlines() if t.strip()]
        result_data = {
            "topic": data.topic,
            "generated_titles": titles,
            "new_titles": []
        }
        save_results(result_data)
        return result_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-new-titles", response_model=TitleResponse)
def generate_alternative_titles(data: NewTitleRequest):
    try:
        new_raw = generate_new_titles(data.topic, data.previous_result)
        new_titles = [t.strip() for t in new_raw.splitlines() if t.strip()]
        result_data = {
            "topic": data.topic,
            "generated_titles": data.previous_result.splitlines(),
            "new_titles": new_titles
        }
        save_results(result_data)
        return result_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-titles")
def get_all_titles():
    try:
        all_titles = load_all_titles()
        return {"history": all_titles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
