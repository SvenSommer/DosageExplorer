# Refactored FastAPI backend for unified structured dosage input
from typing import Optional
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dosage.builder import build_freetext, build_interval, build_interval_with_times, build_mman, build_timeofday, build_weekday, build_weekday_based
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
    return templates.TemplateResponse("result_fragment.html", {"request": request, "fhir": fhir, "text": freetext})

@app.post("/generate/mman", response_class=HTMLResponse)
async def generate_mman(request: Request):
    form = await request.form()
    morning = int(form.get("morning") or 0)
    noon = int(form.get("noon") or 0)
    evening = int(form.get("evening") or 0)
    night = int(form.get("night") or 0)
    duration_value, duration_unit = extract_duration(form)
    medication = form.get("medication") or "Arzneimittel"
    unit = form.get("unit") or "Stück"
    fhir = build_mman(morning, noon, evening, night, duration_value, medication, unit, duration_unit)
    text = generate_dosage_texts(fhir)
    return templates.TemplateResponse("result_fragment.html", {"request": request, "fhir": fhir, "text": text})

@app.post("/generate/timeofday", response_class=HTMLResponse)
async def generate_timeofday(request: Request):
    form = await request.form()
    times, doses = extract_times_and_doses(form)
    duration_value, duration_unit = extract_duration(form)
    medication = form.get("medication") or "Arzneimittel"
    unit = form.get("unit") or "Stück"
    fhir = build_timeofday(times, doses, duration_value, medication, unit, duration_unit)
    text = generate_dosage_texts(fhir)
    return templates.TemplateResponse("result_fragment.html", {"request": request, "fhir": fhir, "text": text})

@app.post("/generate/weekday", response_class=HTMLResponse)
async def generate_weekday(request: Request):
    form = await request.form()
    days_and_doses = [(d, float(form.get(f"dose_{d}"))) for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] if form.get(f"day_{d}") == "1" and form.get(f"dose_{d}")]
    duration_value, duration_unit = extract_duration(form)
    medication = form.get("medication") or "Arzneimittel"
    unit = form.get("unit") or "Stück"
    fhir = build_weekday(days_and_doses, duration_value, duration_unit, medication, unit)
    text = generate_dosage_texts(fhir)
    return templates.TemplateResponse("result_fragment.html", {"request": request, "fhir": fhir, "text": text})

@app.post("/generate/interval", response_class=HTMLResponse)
async def generate_interval(request: Request):
    form = await request.form()
    frequency = int(form.get("frequency"))
    period = int(form.get("period"))
    period_unit = form.get("period_unit")
    duration_value, duration_unit = extract_duration(form)
    medication = form.get("medication") or "Arzneimittel"
    dose = float(form.get("dose") or 1)
    unit = form.get("unit") or "Stück"
    fhir = build_interval(frequency, period, period_unit, duration_value, duration_unit, medication, dose, unit)
    text = generate_dosage_texts(fhir)
    return templates.TemplateResponse("result_fragment.html", {"request": request, "fhir": fhir, "text": text})

@app.post("/generate/combined_interval_time", response_class=HTMLResponse)
async def generate_combined_interval_time(request: Request):
    form = await request.form()
    period = int(form.get("period"))
    period_unit = form.get("period_unit")
    duration_value, duration_unit = extract_duration(form)
    medication = form.get("medication") or "Arzneimittel"
    unit = form.get("unit") or "Stück"
    schedule = extract_schedule(form)
    fhir = build_interval_with_times(schedule, period, period_unit, duration_value, medication, unit, duration_unit)
    text = generate_dosage_texts(fhir)
    return templates.TemplateResponse("result_fragment.html", {"request": request, "fhir": fhir, "text": text})

@app.post("/generate/weekday_combined", response_class=HTMLResponse)
async def generate_weekday_combined(request: Request):
    form = await request.form()
    medication = form.get("medication") or "Arzneimittel"
    unit = form.get("unit") or "Stück"
    duration_value, duration_unit = extract_duration(form)
    entries = []
    i = 1
    while True:
        days = form.getlist(f"days{i}")
        time = form.get(f"time{i}", "").strip()
        when = form.get(f"when{i}", "").strip()
        dose = form.get(f"dose{i}", "").strip()
        if not days and not dose:
            break
        if days and dose and (when or time):
            entries.append({"days": days, "time": time or None, "when": when or None, "dose": float(dose)})
        i += 1
    fhir = build_weekday_based(entries, duration_value, medication, unit, duration_unit)
    text = generate_dosage_texts(fhir)
    return templates.TemplateResponse("result_fragment.html", {"request": request, "fhir": fhir, "text": text})

def extract_duration(form):
    value = form.get("duration_value")
    unit = form.get("duration_unit")
    return (int(value) if value else None, unit if value else None)

def extract_times_and_doses(form):
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
    return times, doses

def extract_schedule(form):
    schedule = []
    i = 1
    while True:
        time_key = f"time{i}"
        dose_key = f"dose{i}"
        if time_key in form and dose_key in form:
            time_val = form.get(time_key).strip()
            dose_val = float(form.get(dose_key).strip() or 0)
            if time_val and dose_val > 0:
                schedule.append((time_val, dose_val))
            i += 1
        else:
            break
    return schedule

def generate_dosage_texts(fhir: dict) -> str:
    generator = GematikDosageTextGenerator()
    texts = [generator.generate_single_dosage_text(dosage) for dosage in fhir.get("dosageInstruction", [])]
    return "<br>".join(filter(None, texts))