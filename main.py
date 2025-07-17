from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dosage.builder import build_freetext, build_mman, build_timeofday
from dosage.text_generator import GematikDosageTextGenerator

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
    text = generate_dosage_texts(fhir)
    return templates.TemplateResponse(
        "result_fragment.html", {"request": request, "fhir": fhir, "text": freetext}
    )

@app.post("/generate/mman", response_class=HTMLResponse)
async def generate_mman(
    request: Request,
    morning: int = Form(0),
    noon: int = Form(0),
    evening: int = Form(0),
    night: int = Form(0),
    duration_days: int = Form(None),
    medication: str = Form("Arzneimittel"),
    dose: float = Form(1),  # wird nicht verwendet, bleibt für Kompatibilität
    unit: str = Form("Stück"),
):
    fhir = build_mman(morning, noon, evening, night, duration_days, medication, unit)
    text = generate_dosage_texts(fhir)
    return templates.TemplateResponse(
        "result_fragment.html", {"request": request, "fhir": fhir, "text": text}
    )

@app.post("/generate/timeofday", response_class=HTMLResponse)
async def generate_timeofday(request: Request):
    form = await request.form()

    times = []
    doses = []
    for key in sorted(form.keys()):
        if key.startswith("time_"):
            idx = key.split("_")[1]
            time = form.get(f"time_{idx}")
            dose = form.get(f"dose_{idx}")
            if time and dose:
                times.append(time)
                doses.append(float(dose))

    duration_days = int(form.get("duration_days") or 0) or None
    medication = form.get("medication") or "Arzneimittel"
    unit = form.get("unit") or "Stück"

    fhir = build_timeofday(times, doses, duration_days, medication, unit)
    text = generate_dosage_texts(fhir)

    return templates.TemplateResponse(
        "result_fragment.html",
        {"request": request, "fhir": fhir, "text": text}
    )

def generate_dosage_texts(fhir: dict) -> str:
    generator = GematikDosageTextGenerator()
    texts = [
        generator.generate_single_dosage_text(dosage)
        for dosage in fhir.get("dosageInstruction", [])
    ]
    return "<br>".join(filter(None, texts))