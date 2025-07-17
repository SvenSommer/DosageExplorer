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


def build_mman(
    morning: int,
    noon: int,
    evening: int,
    night: int,
    duration_days: int = None,
    medication: str = "Arzneimittel",
    dose: float = 1,
    unit: str = "Stück"
) -> dict:
    when_map = {
        "morning": ("MORN", morning),
        "noon": ("NOON", noon),
        "evening": ("EVE", evening),
        "night": ("NIGHT", night)
    }

    selected_times = [code for name, (code, value) in when_map.items() if value > 0]

    dosage = {
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
        "dosageInstruction": [
            {
                "timing": {
                    "repeat": {
                        "when": selected_times,
                        **({"duration": duration_days, "durationUnit": "d"} if duration_days else {})
                    }
                },
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
        ],
    }

    return dosage
