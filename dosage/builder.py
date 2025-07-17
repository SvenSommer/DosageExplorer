from typing import List, Tuple, Optional
from collections import defaultdict

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
                "extension": [
                    {
                        "url": "http://ig.fhir.de/igs/medication/StructureDefinition/GeneratedDosageInstructions",
                        "extension": [
                            {"url": "text", "valueString": text},
                            {
                                "url": "algorithm",
                                "valueCoding": {
                                    "system": "http://ig.fhir.de/igs/medication/CodeSystem/DosageTextAlgorithms",
                                    "version": "1.0.0",
                                    "code": "GermanDosageTextGenerator",
                                },
                            },
                        ],
                    }
                ],
                "text": text,
            }
        ],
    }

def build_timeofday(
    times: List[str],  # Uhrzeiten als "HH:MM" oder "HH:MM:SS"
    doses: List[float],  # Dosis je Uhrzeit, gleiche Länge wie times
    duration_days: Optional[int] = None,
    medication: str = "Arzneimittel",
    unit: str = "Stück",
) -> dict:
    if len(times) != len(doses):
        raise ValueError("Die Anzahl der Uhrzeiten und Dosen muss übereinstimmen.")

    resource = {
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

    # Gruppiere Dosierungen mit identischer Dosis in einer gemeinsamen Dosage-Instanz
    grouped: dict[float, List[str]] = {}
    for time, dose in zip(times, doses):
        time = (
            time if len(time) == 8 else time + ":00"
        )  # normalize "HH:MM" → "HH:MM:00"
        grouped.setdefault(dose, []).append(time)

    for dose, times in grouped.items():
        dosage = {
            "timing": {"repeat": {"timeOfDay": times}},
            "doseAndRate": [
                {
                    "doseQuantity": {
                        "value": dose,
                        "unit": unit,
                        "system": "https://fhir.kbv.de/CodeSystem/KBV_CS_SFHIR_BMP_DOSIEREINHEIT",
                        "code": "1",
                    }
                }
            ],
        }
        if duration_days:
            dosage["timing"]["repeat"]["boundsDuration"] = {
                "value": duration_days,
                "unit": "d",
                "system": "http://unitsofmeasure.org",
                "code": "d",
            }

        resource["dosageInstruction"].append(dosage)

    return resource


def build_mman(
    morning: float = 0,
    noon: float = 0,
    evening: float = 0,
    night: float = 0,
    duration_days: int = None,
    medication: str = "Arzneimittel",
    unit: str = "Stück",
) -> dict:
    """
    Erzeugt ein FHIR-konformes MedicationRequest-Objekt für das MMAN-Schema.
    """

    time_slots = {
        "MORN": morning,
        "NOON": noon,
        "EVE": evening,
        "NIGHT": night,
    }

    # Sammle nur belegte Zeiten
    active_slots = {k: v for k, v in time_slots.items() if v > 0}

    # Basis-Ressource
    resource = {
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

    # Bilde duration falls gesetzt
    bounds = (
        {
            "boundsDuration": {
                "value": duration_days,
                "unit": "d",
                "system": "http://unitsofmeasure.org",
                "code": "d",
            }
        }
        if duration_days
        else {}
    )

    doses = list(active_slots.values())
    same_dose = all(d == doses[0] for d in doses)

    if same_dose:
        # eine Dosage-Instanz mit mehreren Zeitpunkten
        dosage = {
            "timing": {"repeat": {"when": list(active_slots.keys()), **bounds}},
            "doseAndRate": [
                {
                    "doseQuantity": {
                        "value": doses[0],
                        "unit": unit,
                        "system": "https://fhir.kbv.de/CodeSystem/KBV_CS_SFHIR_BMP_DOSIEREINHEIT",
                        "code": "1",
                    }
                }
            ],
        }
        resource["dosageInstruction"].append(dosage)

    else:
        # eigene Instanz je Tageszeit
        for when, value in active_slots.items():
            dosage = {
                "timing": {"repeat": {"when": [when], **bounds}},
                "doseAndRate": [
                    {
                        "doseQuantity": {
                            "value": value,
                            "unit": unit,
                            "system": "https://fhir.kbv.de/CodeSystem/KBV_CS_SFHIR_BMP_DOSIEREINHEIT",
                            "code": "1",
                        }
                    }
                ],
            }
            resource["dosageInstruction"].append(dosage)

    return resource

def build_weekday(
    days_and_doses: List[Tuple[str, float]],
    duration_value: Optional[int] = None,
    duration_unit: str = "wk",  # angepasst!
    medication: str = "Arzneimittel",
    unit: str = "Stück"
) -> dict:
    """
    Erzeugt ein FHIR-konformes MedicationRequest für das Wochentagsschema (dayOfWeek).
    """

    resource = {
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

    bounds = (
        {
            "boundsDuration": {
                "value": duration_value,
                "unit": {
                    "d": "Tag(e)",
                    "wk": "Woche(n)",
                    "mo": "Monat(e)"
                }.get(duration_unit, duration_unit),
                "system": "http://unitsofmeasure.org",
                "code": duration_unit
            }
        }
        if duration_value
        else {}
    )

    # Gruppiere Wochentage nach identischer Dosis
    grouped: dict[float, List[str]] = defaultdict(list)
    for day, dose in days_and_doses:
        grouped[dose].append(day.lower())  # FHIR erwartet "mon", "tue", ...

    for dose, days in grouped.items():
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
            "doseAndRate": [
                {
                    "doseQuantity": {
                        "value": dose,
                        "unit": unit,
                        "system": "https://fhir.kbv.de/CodeSystem/KBV_CS_SFHIR_BMP_DOSIEREINHEIT",
                        "code": "1"
                    }
                }
            ]
        }
        resource["dosageInstruction"].append(dosage)

    return resource
