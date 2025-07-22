from typing import List, Tuple, Optional
from collections import defaultdict

from dosage.dosage_units import resolve_unit_label


def bounds_duration(value: Optional[int], unit: Optional[str]) -> dict:
    if value and unit and unit in {"d", "wk", "mo", "a"}:
        return {
            "boundsDuration": {
                "value": value,
                "unit": {
                    "d": "Tag(e)",
                    "wk": "Woche(n)",
                    "mo": "Monat(e)",
                    "a": "Jahr(e)",
                }[unit],
                "system": "http://unitsofmeasure.org",
                "code": unit,
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
        "dosageInstruction": [
            {
                "text": text,
            }
        ],
    }


def build_timeofday(
    times: List[str],
    doses: List[float],
    units: List[str],
    duration_value: Optional[int],
    medication: str,
    duration_unit: Optional[str],
) -> dict:
    if not (len(times) == len(doses) == len(units)):
        raise ValueError("Uhrzeiten, Dosen und Einheiten müssen gleich lang sein.")

    grouped = defaultdict(list)
    for time, dose, unit in zip(times, doses, units):
        time = time if len(time) == 8 else time + ":00"
        grouped[(dose, unit)].append(time)

    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)

    for (dose, unit), times in grouped.items():
        dosage = {
            "timing": {"repeat": {"timeOfDay": times, **bounds}},
            "doseAndRate": [_dose_quantity(dose, unit)],
        }
        resource["dosageInstruction"].append(dosage)

    return resource


def build_mman(
    morning: Tuple[float, Optional[str]],
    noon: Tuple[float, Optional[str]],
    evening: Tuple[float, Optional[str]],
    night: Tuple[float, Optional[str]],
    duration_value: Optional[int],
    medication: str,
    duration_unit: Optional[str],
) -> dict:
    time_slots = {"MORN": morning, "NOON": noon, "EVE": evening, "NIGHT": night}
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)

    dose_groups = defaultdict(list)
    units_for_dose = {}

    for when, (dose, unit) in time_slots.items():
        if dose > 0:
            key = (dose, unit)
            dose_groups[key].append(when)
            units_for_dose[key] = unit

    for (dose, unit), whens in dose_groups.items():
        dosage = {
            "timing": {"repeat": {"when": whens, **bounds}},
            "doseAndRate": [_dose_quantity(dose, unit)],
        }
        resource["dosageInstruction"].append(dosage)

    return resource


def build_weekday(
    days_and_doses: List[Tuple[str, float, Optional[str]]],
    duration_value: Optional[int],
    duration_unit: Optional[str],
    medication: str
) -> dict:
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)

    grouped = defaultdict(list)
    for day, dose, unit in days_and_doses:
        grouped[(dose, unit)].append(day.lower())

    for (dose, unit), days in grouped.items():
        dosage = {
            "timing": {
                "repeat": {
                    "dayOfWeek": days,
                    "frequency": len(days),
                    "period": 1,
                    "periodUnit": "wk",
                    **bounds
                }
            },
            "doseAndRate": [_dose_quantity(dose, unit)]
        }
        resource["dosageInstruction"].append(dosage)

    return resource



def build_interval(
    frequency: int,
    period: int,
    period_unit: str,
    duration_value: Optional[int],
    duration_unit: Optional[str],
    medication: str,
    dose: float,
    unit: str,
) -> dict:
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)
    dosage = {
        "timing": {
            "repeat": {
                "frequency": frequency,
                "period": period,
                "periodUnit": period_unit,
                **bounds,
            }
        },
        "doseAndRate": [_dose_quantity(dose, unit)],
    }
    resource["dosageInstruction"].append(dosage)
    return resource


def build_interval_with_times(
    schedule: List[Tuple[str, float]],
    period: int,
    period_unit: str,
    duration_value: Optional[int],
    medication: str,
    unit: str,
    duration_unit: Optional[str],
) -> dict:
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)

    for time, dose in schedule:
        timing_field = "timeOfDay" if ":" in time else "when"
        dosage = {
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": period,
                    "periodUnit": period_unit,
                    timing_field: [time],
                    **bounds,
                }
            },
            "doseAndRate": [_dose_quantity(dose, unit)],
        }
        resource["dosageInstruction"].append(dosage)

    return resource


def build_weekday_based(
    entries: List[dict],
    duration_value: Optional[int],
    medication: str,
    unit: str,
    duration_unit: Optional[str],
) -> dict:
    resource = _base_resource(medication)
    bounds = bounds_duration(duration_value, duration_unit)

    for entry in entries:
        days = entry.get("days", [])
        time = entry.get("time")
        when = entry.get("when")
        dose = entry.get("dose", 1.0)
        repeat = {
            "dayOfWeek": days,
            "frequency": len(days),
            "period": 1,
            "periodUnit": "wk",
            **bounds,
        }
        if time:
            repeat["timeOfDay"] = [time]
        elif when:
            repeat["when"] = [when]

        dosage = {
            "timing": {"repeat": repeat},
            "doseAndRate": [_dose_quantity(dose, unit)],
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
        "dosageInstruction": [],
    }


def _dose_quantity(value: float, unit_code: Optional[str]) -> dict:
    return {
        "doseQuantity": {
            "value": value,
            "unit": resolve_unit_label(unit_code),
            "system": "https://fhir.kbv.de/CodeSystem/KBV_CS_SFHIR_BMP_DOSIEREINHEIT",
            "code": unit_code or "1",
        }
    }


