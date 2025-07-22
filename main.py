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
    # Gib die erste Fehlermeldung als Text aus
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
    noon: Optional[str] = Query(default="0"),
    evening: Optional[str] = Query(default="0"),
    night: Optional[str] = Query(default="0"),
    medication: str = "Arzneimittel",
    unit: str = "Stück",
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
        safe_int(morning),
        safe_int(noon),
        safe_int(evening),
        safe_int(night),
        duration,
        medication,
        unit,
        duration_unit
    )
    return render_result(request, fhir_dict, schema="mman")

@app.get("/generate/timeofday", response_class=HTMLResponse)
async def generate_timeofday(
    request: Request,
    time: List[str] = Query(default=[]),
    dose: List[float] = Query(default=[]),
    medication: str = "Arzneimittel",
    unit: str = "Stück",
    duration_value: Optional[str] = Query(default=None),
    duration_unit: Optional[str] = None,
):
    if len(time) != len(set(time)):
        return render_error(request, "❌ Doppelte Uhrzeiten sind nicht erlaubt.", schema="timeofday")

    duration = int(duration_value) if duration_value and duration_value.isdigit() else None
    fhir_dict = build_timeofday(time, dose, duration, medication, unit, duration_unit)
    return render_result(request, fhir_dict, schema="timeofday")

@app.get("/generate/weekday", response_class=HTMLResponse)
async def generate_weekday(
    request: Request,
    dose_mon: Optional[float] = None,
    dose_tue: Optional[float] = None,
    dose_wed: Optional[float] = None,
    dose_thu: Optional[float] = None,
    dose_fri: Optional[float] = None,
    dose_sat: Optional[float] = None,
    dose_sun: Optional[float] = None,
    medication: str = "Arzneimittel",
    unit: str = "Stück",
    duration_value: Optional[str] = Query(default=None),
    duration_unit: Optional[str] = None,
):
    days = [("mon", dose_mon), ("tue", dose_tue), ("wed", dose_wed), ("thu", dose_thu),
            ("fri", dose_fri), ("sat", dose_sat), ("sun", dose_sun)]
    days_and_doses = [(d, v) for d, v in days if v is not None]

    if not days_and_doses:
        return render_error(request, "❌ Bitte geben Sie mindestens für einen Wochentag eine Dosis ein.", schema="weekday")

    duration = int(duration_value) if duration_value and duration_value.isdigit() else None
    fhir_dict = build_weekday(days_and_doses, duration, duration_unit, medication, unit)
    return render_result(request, fhir_dict, schema="weekday")

@app.get("/generate/interval", response_class=HTMLResponse)
async def generate_interval(
    request: Request,
    frequency: int,
    period: int,
    period_unit: str,
    dose: float = 1,
    medication: str = "Arzneimittel",
    unit: str = "Stück",
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