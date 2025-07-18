from typing import Optional
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dosage.builder import build_freetext, build_interval, build_interval_with_times, build_mman, build_timeofday, build_weekday
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

@app.post("/generate/weekday", response_class=HTMLResponse)
async def generate_weekday(request: Request):
    form = await request.form()

    days_and_doses = []
    for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
        if form.get(f"day_{day}") == "1":
            try:
                dose = float(form.get(f"dose_{day}", 0))
                if dose > 0:
                    days_and_doses.append((day, dose))
            except ValueError:
                continue  # ignorieren, wenn Eingabe fehlerhaft

    medication = form.get("medication") or "Arzneimittel"
    unit = form.get("unit") or "Stück"

    duration_unit = "wk"  # Fest für dieses Schema
    duration_value = int(form.get("duration_value") or 0) or None
    duration_unit = form.get("duration_unit") or "wk"
    fhir = build_weekday(
        days_and_doses,
        duration_value=duration_value,
        duration_unit=duration_unit,
        medication=medication,
        unit=unit
    )
    text = generate_dosage_texts(fhir)

    return templates.TemplateResponse(
        "result_fragment.html", {"request": request, "fhir": fhir, "text": text}
    )

@app.post("/generate/interval", response_class=HTMLResponse)
async def generate_interval(request: Request):
    form = await request.form()
    frequency = int(form.get("frequency"))
    period = int(form.get("period"))
    period_unit = form.get("period_unit")

    duration_value = form.get("duration_value")
    duration_unit = form.get("duration_unit")

    duration_value = int(duration_value) if duration_value else None
    duration_unit = duration_unit if duration_value else None

    medication = form.get("medication") or "Arzneimittel"
    dose = float(form.get("dose") or 1)
    unit = form.get("unit") or "Stück"

    fhir = build_interval(
        frequency=frequency,
        period=period,
        period_unit=period_unit,
        duration_value=duration_value,
        duration_unit=duration_unit,
        medication=medication,
        dose=dose,
        unit=unit,
    )
    text = generate_dosage_texts(fhir)

    return templates.TemplateResponse(
        "result_fragment.html", {"request": request, "fhir": fhir, "text": text}
    )

@app.post("/generate/combined_interval_time", response_class=HTMLResponse)
async def generate_interval_timed(request: Request):
    form = await request.form()

    period = int(form.get("period"))
    period_unit = form.get("period_unit")

    duration_value = form.get("duration_value")
    duration_unit = form.get("duration_unit")

    duration_value = int(duration_value) if duration_value else None
    duration_unit = duration_unit if duration_value else None

    medication = form.get("medication") or "Arzneimittel"
    unit = form.get("unit") or "Stück"

    # Mehrere Zeitpunkte & Dosierungen
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

    fhir = build_interval_with_times(
        schedule=schedule,
        period=period,
        period_unit=period_unit,
        duration_days=duration_value if duration_unit == "d" else None,  # aktuell nur Tag-basierte Begrenzung
        medication=medication,
        unit=unit,
    )

    text = generate_dosage_texts(fhir)

    return templates.TemplateResponse(
        "result_fragment.html", {"request": request, "fhir": fhir, "text": text}
    )



def generate_dosage_texts(fhir: dict) -> str:
    generator = GematikDosageTextGenerator()
    texts = [
        generator.generate_single_dosage_text(dosage)
        for dosage in fhir.get("dosageInstruction", [])
    ]
    return "<br>".join(filter(None, texts))