# routers/layout.py

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from utils.input_layout import LayoutExtractor
from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="templates")
router = APIRouter()

extractor = LayoutExtractor()

@router.get("/layout-ui", response_class=HTMLResponse)
async def layout_ui(request: Request):
    return templates.TemplateResponse("layout_selection.html", {"request": request})


@router.post("/layout-from-url", response_class=HTMLResponse)
async def layout_from_url(request: Request, url: str = Form(...), search_context: str = Form(default="")):
    layout = extractor.extract_layout(url, search_context)
    return templates.TemplateResponse("layout_selection.html", {
        "request": request,
        "layout": layout,
        "layout_type": "url"
    })


@router.post("/layout-default", response_class=HTMLResponse)
async def layout_default(
    request: Request,
    topic: str = Form(...),
    title: str = Form(...),
    content_type: str = Form(...),
    search_context: str = Form(...)
):
    layout = extractor.default_layout(topic, title, content_type, search_context)
    return templates.TemplateResponse("layout_selection.html", {
        "request": request,
        "layout": layout,
        "layout_type": "default"
    })


@router.post("/layout-custom", response_class=HTMLResponse)
async def layout_custom(
    request: Request,
    custom_instructions: str = Form(...),
    search_context: str = Form(...)
):
    layout = extractor.custom_layout(custom_instructions, search_context)
    return templates.TemplateResponse("layout_selection.html", {
        "request": request,
        "layout": layout,
        "layout_type": "custom"
    })

