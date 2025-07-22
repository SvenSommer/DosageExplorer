from typing import List, Tuple, Optional
from collections import defaultdict

def bounds_duration(value: Optional[int], unit: Optional[str]) -> dict:
    if value and unit and unit in {"d", "wk", "mo", "a"}:
        return {
            "boundsDuration": {
                "value": value,
                "unit": {
                    "d": "Tag(e)",
                    "wk": "Woche(n)",
                    "mo": "Monat",
                    "a": "Jahr(e)"
                }[unit],
                "system": "http://unitsofmeasure.org",
                "code": unit
            }
        }
    return {}

def build_freetext(text: str) -> dict:
    return {
        "resourceType": "MedicationRequest",
        "meta": {
            "profile": [
                "http://ig.fhir.de/igs/medication/StructureDefinition/MedicationRequestDgMP"
            ]
        },
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {"text": "Ibuprofen 400mg"},
        "subject": {"display": "Patient"},
        "dosageInstruction": [{
            "text": text,
        }],
    }

def build_timeofday(times: List[str], doses: List[float], duration_value: Optional[int], medication: str, unit: str, duration_unit: Optional[str]) -> dict:
    if len(times) != len(doses):
        raise ValueError("Uhrzeiten und Dosen müssen gleich lang sein.")

    grouped: dict[float, List[str]] = defaultdict(list)
    for time, dose in zip(times, doses):
        time = time if len(time) == 8 else time + ":00"
        grouped[dose].append(time)

    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)

    for dose, times in grouped.items():
        dosage = {
            "timing": {"repeat": {"timeOfDay": times, **bounds}},
            "doseAndRate": [_dose_quantity(dose, unit)]
        }
        resource["dosageInstruction"].append(dosage)

    return resource


def build_mman(morning: float, noon: float, evening: float, night: float, duration_value: Optional[int], medication: str, unit: str, duration_unit: Optional[str]) -> dict:
    time_slots = {"MORN": morning, "NOON": noon, "EVE": evening, "NIGHT": night}
    active = {k: v for k, v in time_slots.items() if v > 0}
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)

    # Gruppiere Tageszeiten nach Dosis
    dose_groups = defaultdict(list)
    for when, dose in active.items():
        dose_groups[dose].append(when)

    for dose, whens in dose_groups.items():
        dosage = {
            "timing": {"repeat": {"when": whens, **bounds}},
            "doseAndRate": [_dose_quantity(dose, unit)]
        }
        resource["dosageInstruction"].append(dosage)

    return resource

def build_weekday(days_and_doses: List[Tuple[str, float]], duration_value: Optional[int], duration_unit: Optional[str], medication: str, unit: str) -> dict:
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)
    grouped: dict[float, List[str]] = defaultdict(list)
    for day, dose in days_and_doses:
        grouped[dose].append(day.lower())

    for dose, days in grouped.items():
        dosage = {
            "timing": {"repeat": {"dayOfWeek": days, "frequency": len(days), "period": 1, "periodUnit": "wk", **bounds}},
            "doseAndRate": [_dose_quantity(dose, unit)]
        }
        resource["dosageInstruction"].append(dosage)

    return resource

def build_interval(frequency: int, period: int, period_unit: str, duration_value: Optional[int], duration_unit: Optional[str], medication: str, dose: float, unit: str) -> dict:
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)
    dosage = {
        "timing": {"repeat": {"frequency": frequency, "period": period, "periodUnit": period_unit, **bounds}},
        "doseAndRate": [_dose_quantity(dose, unit)]
    }
    resource["dosageInstruction"].append(dosage)
    return resource

def build_interval_with_times(schedule: List[Tuple[str, float]], period: int, period_unit: str, duration_value: Optional[int], medication: str, unit: str, duration_unit: Optional[str]) -> dict:
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)

    for time, dose in schedule:
        timing_field = "timeOfDay" if ":" in time else "when"
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": period, "periodUnit": period_unit, timing_field: [time], **bounds}},
            "doseAndRate": [_dose_quantity(dose, unit)]
        }
        resource["dosageInstruction"].append(dosage)

    return resource

def build_weekday_based(entries: List[dict], duration_value: Optional[int], medication: str, unit: str, duration_unit: Optional[str]) -> dict:
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)

    for entry in entries:
        days = entry.get("days", [])
        time = entry.get("time")
        when = entry.get("when")
        dose = entry.get("dose", 1.0)
        repeat = {"dayOfWeek": days, "frequency": len(days), "period": 1, "periodUnit": "wk", **bounds}
        if time:
            repeat["timeOfDay"] = [time]
        elif when:
            repeat["when"] = [when]

        dosage = {
            "timing": {"repeat": repeat},
            "doseAndRate": [_dose_quantity(dose, unit)]
        }
        resource["dosageInstruction"].append(dosage)

    return resource

def _base_resource(medication: str) -> dict:
    return {
        "resourceType": "MedicationRequest",
        "meta": {
            "profile": [
                "http://ig.fhir.de/igs/medication/StructureDefinition/MedicationRequestDgMP"
            ]
        },
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {"text": medication},
        "subject": {"display": "Patient"},
        "dosageInstruction": []
    }

def _dose_quantity(value: float, unit: str) -> dict:
    return {
        "doseQuantity": {
            "value": value,
            "unit": unit,
            "system": "https://fhir.kbv.de/CodeSystem/KBV_CS_SFHIR_BMP_DOSIEREINHEIT",
            "code": "1"
        }
    }