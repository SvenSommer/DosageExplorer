# dosage/units.py

from pathlib import Path
import re
from typing import Optional

UNITS_FILE = Path(__file__).parent.parent / "templates" / "_dosage_units.jinja"

def get_dosage_unit_mapping() -> dict[str, str]:
    text = UNITS_FILE.read_text(encoding="utf-8")
    pattern = r'\("([^"]+)",\s*"([^"]+)"\)'
    return dict(re.findall(pattern, text))

def resolve_unit_label(code: Optional[str]) -> str:
    units = get_dosage_unit_mapping()
    return units.get(code or "", code or "")
