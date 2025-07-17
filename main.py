from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dosage.builder import build_freetext, build_mman

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request, schema: str = Query(default="freetext")):
    return templates.TemplateResponse("index.html", {"request": request, "schema": schema})

@app.get("/form", response_class=HTMLResponse)
async def get_form(request: Request, schema: str = Query(default="freetext")):
    return templates.TemplateResponse("form_fragment.html", {"request": request, "schema": schema})


@app.post("/generate/freetext", response_class=HTMLResponse)
async def generate_freetext(request: Request, freetext: str = Form(...)):
    fhir = build_freetext(freetext)
    return templates.TemplateResponse("result_fragment.html", {"request": request, "fhir": fhir})

@app.post("/generate/mman", response_class=HTMLResponse)
async def generate_mman(
    request: Request,
    morning: int = Form(0),
    noon: int = Form(0),
    evening: int = Form(0),
    night: int = Form(0),
    duration_days: int = Form(None)
):
    fhir = build_mman(morning, noon, evening, night, duration_days)
    return templates.TemplateResponse("result_fragment.html", {"request": request, "fhir": fhir})