from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
from fastapi.responses import RedirectResponse
from urllib.parse import quote
from typing import List, Dict, Any

# Import routers and utilities
from routes import title, search, summarize
from utils.title_generator import title_generate
from routes.search import search_content
from models.schemas import SearchRequest
from routes.summarize import summarize_links
from routes.summarize import SummarizeLinksRequest
from utils.input_layout import LayoutExtractor
from utils.content_generation import generate_content
from utils.enhancing import refine_content 

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="Content Pipeline API",
    version="1.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include route modules with prefixes
app.include_router(title.router, prefix="/content")
app.include_router(search.router, prefix="/content")
app.include_router(summarize.router, prefix="/api")

# ------------------- UI ROUTES -------------------

@app.get("/")
async def get_home(request: Request):
    return templates.TemplateResponse("generate_titles.html", {
        "request": request,
        "titles": [],
        "generated": False,
        "all_titles": [],
        "selected_title": "",
        "topic": ""
    })


@app.post("/generate")
async def generate_titles_view(request: Request, topic: str = Form(...)):
    titles = title_generate(topic)
    return templates.TemplateResponse("generate_titles.html", {
        "request": request,
        "titles": titles,
        "topic": topic,
        "generated": True,
        "all_titles": [titles],
        "selected_title": ""
    })


@app.post("/generate-new")
async def generate_new_titles_view(request: Request, topic: str = Form(...), all_titles: str = Form(...)):
    try:
        all_titles_loaded = json.loads(all_titles)
        if isinstance(all_titles_loaded, str):
            all_titles_loaded = json.loads(all_titles_loaded)
    except Exception as e:
        print("Error loading all_titles:", e)
        all_titles_loaded = []

    new_titles = title_generate(topic)
    updated_all_titles = all_titles_loaded + [new_titles]

    return templates.TemplateResponse("generate_titles.html", {
        "request": request,
        "titles": new_titles,
        "topic": topic,
        "generated": True,
        "all_titles": updated_all_titles,
        "selected_title": ""
    })


@app.post("/confirm-title")
async def confirm_title_view(
    request: Request,
    selected_title: str = Form(...),
    custom_title: str = Form(""),
    topic: str = Form(""),
    all_titles: str = Form("")
):
    final_title = custom_title.strip() if custom_title.strip() else selected_title
    print(f"✅ Final selected title: {final_title} on topic {topic}")

    # Redirect to search stage
    # ✅ Correct
    redirect_url = f"/search-ui?topic={topic}&title={final_title}"
    return RedirectResponse(url=redirect_url, status_code=303)


# ------------------- SEARCH + SUMMARIZATION UI -------------------

@app.get("/search-ui", response_class=HTMLResponse)
async def search_ui(request: Request, topic: str = "", title: str = ""):
    return templates.TemplateResponse("search_and_summarize.html", {
        "request": request,
        "topic": topic,  # This is used for searching
        "title": title,  # This can be displayed or used later
        "search_results": None,
        "summary": None
    })

@app.post("/search-ui", response_class=HTMLResponse)
async def search_ui_post(
    request: Request,
    topic: str = Form(...),
    title: str = Form(...),  # retain the title across form submissions
    num_results: int = Form(5)
):
    try:
        # Use our search functionality
        from utils.internet_search import search_topic
        search_results = search_topic(topic, num_results)
        
        # Format results for display
        formatted_results = []
        for result in search_results:
            formatted_results.append({
                "title": result["title"],
                "url": result["url"],
                "snippet": result["snippet"]
            })
        
        return templates.TemplateResponse("search_results.html", {
            "request": request,
            "topic": topic,
            "title": title,
            "results": formatted_results,
            "num_results": num_results
        })
    except Exception as e:
        print(f"Error in search: {str(e)}")
        return templates.TemplateResponse("search_results.html", {
            "request": request,
            "topic": topic,
            "title": title,
            "results": [],
            "num_results": num_results,
            "error": str(e)
        })

@app.post("/summarize-ui", response_class=HTMLResponse)
async def summarize_ui(
    request: Request,
    topic: str = Form(...),
    selected_links: list[str] = Form(default=[]),
    custom_urls: str = Form(default=""),
    custom_research: str = Form(default=""),
    title: str = Form(default="")
):
    try:
        # Combine all links: selected + custom
        links = selected_links.copy()
        if custom_urls.strip():
            additional_links = [url.strip() for url in custom_urls.split(",") if url.strip()]
            links.extend(additional_links)

        summary_parts = []

        # Summarize from links (if any)
        if links:
            summary_request = SummarizeLinksRequest(topic=topic, links=links)
            link_summary = summarize_links(summary_request)
            summary_parts.append(f"🔗 Summary from URLs:\n{link_summary}")

        # Summarize custom research text (if any)
        if custom_research.strip():
            summary_parts.append(f"📝 Summary from User Research:\n{custom_research.strip()}")

        # Join all parts
        full_summary = "\n\n".join(summary_parts)

    except Exception as e:
        return templates.TemplateResponse("search_and_summarize.html", {
            "request": request,
            "topic": topic,
            "search_results": [],
            "summary": "",
            "error": f"Failed to summarize: {e}"
        })

    # Redirect to the layout selection page
    redirect_url = f"/layout-ui?topic={topic}&title={topic}&summary={full_summary}"
    return RedirectResponse(url=redirect_url, status_code=303)

# ------------------- LAYOUT UI ROUTE -------------------

@app.get("/layout-ui", response_class=HTMLResponse)
async def layout_ui(request: Request, topic: str = "", title: str = "", summary: str = ""):
    return templates.TemplateResponse("layout_selection.html", {
        "request": request,
        "topic": topic,
        "title": title,
        "summary": summary,
        "layout": "",
        "confirmed": False
    })

@app.post("/layout-ui")
async def layout_ui_handler(
    request: Request,
    content_type: str = Form(None),
    layout_generator: str = Form(...),
    topic: str = Form(None),
    title: str = Form(None),
    summary: str = Form(None),
    url: str = Form(None),
    custom_instructions: str = Form(None),
    additional_info: str = Form("")  # Add this parameter with default empty string
):
    if not all([topic, title, summary]):
        raise HTTPException(status_code=400, detail="Missing required fields.")
    
    layout = None
    confirmed = False
    le = LayoutExtractor()

    if layout_generator == "Generate Layout":
        if not all([topic, title, summary, content_type]):
            raise HTTPException(status_code=400, detail="Missing fields for default layout generation.")
        layout = le.default_layout(topic, title, content_type, summary)

    elif layout_generator == "Custom layout":
        if not all([custom_instructions, summary]):
            raise HTTPException(status_code=400, detail="Missing fields for custom layout generation.")
        # Pass additional_info with default empty string
        layout = le.custom_layout(custom_instructions, summary, additional_info)

    elif layout_generator == "URL layout":
        if not url:
            raise HTTPException(status_code=400, detail="URL is required for URL layout.")
        layout = le.extract_layout(url, summary)  # Pass summary as research context

    # Ensure the layout is returned as a list of dictionaries
    if not isinstance(layout, list):
        raise HTTPException(status_code=400, detail="Layout must be a list of dictionaries.")

    return templates.TemplateResponse("layout_selection.html", {
        "request": request,
        "topic": topic,
        "title": title,
        "summary": summary,
        "layout": layout,
        "confirmed": confirmed,
        "content_type": content_type
    })

@app.post("/confirm_layout")
async def confirm_layout(
    request: Request,
    topic: str = Form(...),
    title: str = Form(...),
    summary: str = Form(...),
    layout: str = Form(...),
    content_type: str = Form(...),
    additional_info: str = Form(default="")  # Add this
):
    try:
        layout_data = json.loads(layout)
        layout_json = quote(json.dumps(layout_data))
        summary_encoded = quote(summary)
        additional_info_encoded = quote(additional_info)  # Add this

        redirect_url = (
            f"/generate_content_page?"
            f"topic={quote(topic)}"
            f"&title={quote(title)}"
            f"&summary={summary_encoded}"
            f"&layout={layout_json}"
            f"&content_type={quote(content_type)}"
            f"&additional_info={additional_info_encoded}"  # Add this
        )
        return RedirectResponse(url=redirect_url, status_code=303)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid layout JSON: {str(e)}")

@app.get("/generate_content_page", response_class=HTMLResponse)
async def get_generate_content_page(
    request: Request,
    topic: str,
    title: str,
    summary: str,
    layout: str,
    content_type: str
):
    return templates.TemplateResponse("generate_content.html", {
        "request": request,
        "topic": topic,
        "title": title,
        "summary": summary,
        "layout": layout,
        "content_type": content_type
    })


@app.post("/generate_content", response_class=HTMLResponse)
async def post_generate_content(
    request: Request,
    topic: str = Form(...),
    title: str = Form(...),
    summary: str = Form(...),
    layout: str = Form(...),
    content_type: str = Form(...),
    tone: str = Form(...),
    additional_info: str = Form(default="")  # Add this parameter
):
    try:
        # Parse the layout JSON string
        try:
            parsed_layout = json.loads(layout)
            if isinstance(parsed_layout, str):
                # Handle double-encoded JSON
                parsed_layout = json.loads(parsed_layout)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid layout JSON: {str(e)}")

        # Validate layout structure
        if not isinstance(parsed_layout, list):
            raise ValueError("Layout must be a list")

        # Generate content
        content = generate_content(
            topic=topic,
            title=title,
            research_info=summary,
            layout=parsed_layout,
            content_type=content_type,
            tone=tone,
            additional_info=additional_info  # Add this parameter
        )

        return templates.TemplateResponse("final_output.html", {
            "request": request,
            "title": title,
            "content": content,
            "layout": layout,
            "summary": summary,
            "tone": tone,
            "topic": topic,
            "additional_info": additional_info,  # Add this
            "search_context": summary
        })

    except Exception as e:
        print(f"Error in generate_content: {str(e)}")
        return HTMLResponse(
            content=f"<h2>Something went wrong: {str(e)}</h2>",
            status_code=500
        )
    
        
@app.get("/refine-content-ui", response_class=HTMLResponse)
async def get_refine_content_ui(
    request: Request,
    topic: str,
    title: str,
    layout: str,
    summary: str,
    generated_content: str
):
    try:
        return templates.TemplateResponse("refine_content.html", {
            "request": request,
            "topic": topic,
            "title": title,
            "layout": layout,
            "summary": summary,
            "generated_content": generated_content,
        })
    except Exception as e:
        print(f"Error in get_refine_content_ui: {str(e)}")  # Add debugging
        return HTMLResponse(
            content=f"<h2>Something went wrong: {str(e)}</h2>",
            status_code=500
        )

@app.post("/refine-content", response_class=HTMLResponse)
async def post_refine_content(
    request: Request,
    topic: str = Form(...),
    title: str = Form(...),
    layout: str = Form(...),
    summary: str = Form(...),
    generated_content: str = Form(...),
    tone: str = Form(...),
    use_layout: str = Form(default=False),
    use_research: str = Form(default=False),
    additional_instructions: str = Form(default="")
):
    try:
        # Convert checkbox values to boolean
        use_layout_bool = use_layout == "on"
        use_research_bool = use_research == "on"

        refined = refine_content(
            generated_content=generated_content,
            use_layout_instructions=use_layout_bool,
            use_research_context=use_research_bool,
            layout=layout,
            research_context=summary,
            additional_instructions=additional_instructions,
            tone=tone
        )

        return templates.TemplateResponse("final_output.html", {
            "request": request,
            "title": title,
            "content": refined,
            "layout": layout,
            "summary": summary,
            "tone": tone,
            "topic": topic
        })

    except Exception as e:
        print(f"Error in refine_content: {str(e)}")  # Add this for debugging
        return HTMLResponse(
            content=f"<h2>Something went wrong: {str(e)}</h2>",
            status_code=500
        )