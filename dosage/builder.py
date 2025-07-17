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
    morning: float = 0,
    noon: float = 0,
    evening: float = 0,
    night: float = 0,
    duration_days: int = None,
    medication: str = "Arzneimittel",
    unit: str = "Stück"
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
                "code": "d"
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
            "timing": {
                "repeat": {
                    "when": list(active_slots.keys()),
                    **bounds
                }
            },
            "doseAndRate": [
                {
                    "doseQuantity": {
                        "value": doses[0],
                        "unit": unit,
                        "system": "https://fhir.kbv.de/CodeSystem/KBV_CS_SFHIR_BMP_DOSIEREINHEIT",
                        "code": "1"
                    }
                }
            ]
        }
        resource["dosageInstruction"].append(dosage)

    else:
        # eigene Instanz je Tageszeit
        for when, value in active_slots.items():
            dosage = {
                "timing": {
                    "repeat": {
                        "when": [when],
                        **bounds
                    }
                },
                "doseAndRate": [
                    {
                        "doseQuantity": {
                            "value": value,
                            "unit": unit,
                            "system": "https://fhir.kbv.de/CodeSystem/KBV_CS_SFHIR_BMP_DOSIEREINHEIT",
                            "code": "1"
                        }
                    }
                ]
            }
            resource["dosageInstruction"].append(dosage)

    return resource