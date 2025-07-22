from typing import Optional, List
import json
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import HTMLResponse
from fastapi.encoders import jsonable_encoder
from fastapi import status
from starlette.requests import Request as StarletteRequest
from dosage.builder import (
    build_freetext, build_interval, build_interval_with_times,
    build_mman, build_timeofday, build_weekday, build_weekday_based
)
from dosage.text_generator import GematikDosageTextGenerator

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: StarletteRequest, exc: RequestValidationError):
    first_error = exc.errors()[0]
    error_message = f"❌ {first_error.get('msg')}"
    schema = request.query_params.get("schema", "freetext")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "schema": schema,
        "fhir": None,
        "text": error_message,
    }, status_code=status.HTTP_400_BAD_REQUEST)

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request, schema: str = Query(default="freetext")):
    return templates.TemplateResponse("index.html", {"request": request, "schema": schema})

@app.get("/generate/freetext", response_class=HTMLResponse)
async def generate_freetext(request: Request, freetext: str):
    fhir_dict = build_freetext(freetext)
    return render_result(request, fhir_dict, schema="freetext")

@app.get("/generate/mman", response_class=HTMLResponse)
async def generate_mman(
    request: Request,
    morning: Optional[str] = Query(default="0"),
    unit_morning: Optional[str] = None,
    noon: Optional[str] = Query(default="0"),
    unit_noon: Optional[str] = None,
    evening: Optional[str] = Query(default="0"),
    unit_evening: Optional[str] = None,
    night: Optional[str] = Query(default="0"),
    unit_night: Optional[str] = None,
    medication: str = "Arzneimittel",
    duration_value: Optional[str] = Query(default=None),
    duration_unit: Optional[str] = None,
):
    def safe_int(value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    duration = int(duration_value) if duration_value and duration_value.isdigit() else None
    fhir_dict = build_mman(
        (safe_int(morning), unit_morning),
        (safe_int(noon), unit_noon),
        (safe_int(evening), unit_evening),
        (safe_int(night), unit_night),
        duration,
        medication,
        duration_unit
    )
    return render_result(request, fhir_dict, schema="mman")

@app.get("/generate/timeofday", response_class=HTMLResponse)
async def generate_timeofday(
    request: Request,
    time: List[str] = Query(default=[]),
    dose: List[float] = Query(default=[]),
    unit: List[str] = Query(default=[]),
    medication: str = "Arzneimittel",
    duration_value: Optional[str] = Query(default=None),
    duration_unit: Optional[str] = None,
):
    if len(time) != len(set(time)):
        return render_error(request, "❌ Doppelte Uhrzeiten sind nicht erlaubt.", schema="timeofday")

    if not (len(time) == len(dose) == len(unit)):
        return render_error(request, "❌ Uhrzeiten, Dosen und Einheiten müssen jeweils gleich viele Einträge enthalten.", schema="timeofday")

    duration = int(duration_value) if duration_value and duration_value.isdigit() else None
    fhir_dict = build_timeofday(time, dose, unit, duration, medication, duration_unit)
    return render_result(request, fhir_dict, schema="timeofday")

@app.get("/generate/weekday", response_class=HTMLResponse)
async def generate_weekday(
    request: Request,
    dose_mon: Optional[float] = None,
    unit_mon: Optional[str] = None,
    dose_tue: Optional[float] = None,
    unit_tue: Optional[str] = None,
    dose_wed: Optional[float] = None,
    unit_wed: Optional[str] = None,
    dose_thu: Optional[float] = None,
    unit_thu: Optional[str] = None,
    dose_fri: Optional[float] = None,
    unit_fri: Optional[str] = None,
    dose_sat: Optional[float] = None,
    unit_sat: Optional[str] = None,
    dose_sun: Optional[float] = None,
    unit_sun: Optional[str] = None,
    medication: str = "Arzneimittel",
    duration_value: Optional[str] = Query(default=None),
    duration_unit: Optional[str] = None,
):
    days = [
        ("mon", dose_mon, unit_mon),
        ("tue", dose_tue, unit_tue),
        ("wed", dose_wed, unit_wed),
        ("thu", dose_thu, unit_thu),
        ("fri", dose_fri, unit_fri),
        ("sat", dose_sat, unit_sat),
        ("sun", dose_sun, unit_sun)
    ]
    days_and_doses = [(d, v, u) for d, v, u in days if v is not None]

    if not days_and_doses:
        return render_error(request, "❌ Bitte geben Sie mindestens für einen Wochentag eine Dosis ein.", schema="weekday")

    duration = int(duration_value) if duration_value and duration_value.isdigit() else None
    fhir_dict = build_weekday(days_and_doses, duration, duration_unit, medication)
    return render_result(request, fhir_dict, schema="weekday")

@app.get("/generate/interval", response_class=HTMLResponse)
async def generate_interval(
    request: Request,
    frequency: int,
    period: int,
    period_unit: str,
    dose: float = 1,
    unit: str = "Stück",
    medication: str = "Arzneimittel",
    duration_value: Optional[str] = Query(default=None),
    duration_unit: Optional[str] = None,
):
    duration = int(duration_value) if duration_value and duration_value.isdigit() else None
    fhir_dict = build_interval(frequency, period, period_unit, duration, duration_unit, medication, dose, unit)
    return render_result(request, fhir_dict, schema="interval")

# Helper functions

def render_result(request: Request, fhir: dict, schema: str):
    fhir_json = json.dumps(fhir, indent=2, ensure_ascii=False)
    text = generate_dosage_texts(fhir)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "fhir": fhir_json,
        "text": text,
        "schema": schema
    })

def render_error(request: Request, message: str, schema: str):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "fhir": None,
        "text": message,
        "schema": schema
    })

def generate_dosage_texts(fhir: dict) -> str:
    generator = GematikDosageTextGenerator()
    texts = [generator.generate_single_dosage_text(d) for d in fhir.get("dosageInstruction", [])]
    return "<br>".join(filter(None, texts))