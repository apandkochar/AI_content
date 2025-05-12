from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.enhancing import refine_content  # import your function
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/refine", response_class=HTMLResponse)
async def show_refine_page(
    request: Request,
    generated_content: str,
    layout: Optional[str] = "",
    research_context: Optional[str] = "",
    tone: Optional[str] = "neutral"
):
    return templates.TemplateResponse("refine_content.html", {
        "request": request,
        "generated_content": generated_content,
        "layout": layout,
        "research_context": research_context,
        "tone": tone
    })


@router.post("/refine", response_class=HTMLResponse)
async def process_refine(
    request: Request,
    generated_content: str = Form(...),
    layout: str = Form(""),
    research_context: str = Form(""),
    tone: str = Form("neutral"),
    additional_instructions: str = Form(""),
    use_layout: Optional[bool] = Form(False),
    use_research: Optional[bool] = Form(False),
):
    # Call refine_content with flags
    refined = refine_content(
        generated_content=generated_content,
        use_layout_instructions=use_layout,
        use_research_context=use_research,
        layout=layout,
        research_context=research_context,
        additional_instructions=additional_instructions,
        tone=tone
    )

    return templates.TemplateResponse("refined_result.html", {
        "request": request,
        "refined_content": refined
    })
