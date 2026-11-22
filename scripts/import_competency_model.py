"""Import the official competency model (Model_kompetencji.xlsx) into YAML.

The workbook (provided by MC BDG) contains a summary sheet and one sheet per competency
with behavioural indicators described on 5 levels. The output YAML is the single source of
truth consumed by :mod:`kompas.competency`.

Usage::

    uv run --extra import python scripts/import_competency_model.py \
        --materials "[Ministerstwo Cyfryzacji - Biuro Dyrektora generalnego] Kompas Kompetencji"

``--materials`` may point to a folder containing ``HackNation.zip`` or ``Model_kompetencji.xlsx``
(searched recursively) or directly to the xlsx file.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import unicodedata
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "competency_model" / "model_kompetencji.yaml"
LEVEL_POINTS = [1, 3, 5, 7, 9]

# Stable ids used across configuration (config/forms.yaml) and API.
COMPETENCY_IDS: dict[str, str] = {
    "RZETELNOŚĆ": "rzetelnosc",
    "KOMUNIKACJA": "komunikacja",
    "WYKORZYSTYWANIE WIEDZY I DOSKONALENIE ZAWODOWE": "wykorzystywanie_wiedzy",
    "ORGANIZACJA PRACY I ORIENTACJA NA OSIĄGANIE CELÓW": "organizacja_pracy",
    "KREATYWNOŚĆ": "kreatywnosc",
    "WSPÓŁPRACA": "wspolpraca",
    "MYŚLENIE ANALITYCZNE": "myslenie_analityczne",
    "NEGOCJOWANIE": "negocjowanie",
    "WYSTĄPIENIA PUBLICZNE": "wystapienia_publiczne",
    "ORIENTACJA NA KLIENTA/INTERESANTA": "orientacja_na_klienta",
    "RADZENIE SOBIE W SYTUACJACH KRYZYSOWYCH": "radzenie_sobie_w_kryzysie",
    "ZARZĄDZANIE STRATEGICZNE": "zarzadzanie_strategiczne",
    "ZARZĄDZANIE LUDŹMI": "zarzadzanie_ludzmi",
    "PODEJMOWANIE DECYZJI I ODPOWIEDZIALNOŚĆ": "podejmowanie_decyzji",
}


def slugify(text: str) -> str:
    """ASCII slug used as fallback id for unknown competencies."""
    normalized = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
    ascii_text = normalized.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def clean(value: Any) -> str:
    """Collapse whitespace/newlines inside a cell."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def locate_workbook(materials: Path) -> bytes:
    """Return the xlsx bytes from a file, a folder or a zip archive inside the folder."""
    if materials.is_file() and materials.suffix == ".xlsx":
        return materials.read_bytes()
    candidates = list(materials.rglob("Model_kompetencji.xlsx"))
    if candidates:
        return candidates[0].read_bytes()
    for archive in materials.rglob("*.zip"):
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                if name.endswith("Model_kompetencji.xlsx"):
                    return zf.read(name)
    raise FileNotFoundError(f"Model_kompetencji.xlsx not found in {materials}")


def parse_workbook(content: bytes) -> dict[str, Any]:
    """Parse the workbook into the YAML-ready competency model structure."""
    import openpyxl  # imported lazily – optional dependency group "import"

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    summary = wb.worksheets[0]
    guidance = [clean(summary[f"A{row}"].value) for row in (4, 5, 6) if summary[f"A{row}"].value]

    competencies: list[dict[str, Any]] = []
    for ws in wb.worksheets[1:]:
        name = clean(ws["A1"].value)
        comp_id = COMPETENCY_IDS.get(name.upper(), slugify(name))
        indicators = []
        for idx, row in enumerate(ws.iter_rows(min_row=4, max_col=6, values_only=True), start=1):
            if not row or not row[0]:
                continue
            indicators.append(
                {
                    "id": f"{comp_id}.{idx}",
                    "name": clean(row[0]),
                    "levels": {
                        points: clean(text) for points, text in zip(LEVEL_POINTS, row[1:6], strict=True)
                    },
                }
            )
        competencies.append({"id": comp_id, "name": name, "indicators": indicators})

    total = sum(len(c["indicators"]) for c in competencies)
    return {
        "name": "Model kompetencji – służba cywilna",
        "version": date.today().isoformat(),
        "source": "Model_kompetencji.xlsx (MC BDG, HackNation 2026)",
        "guidance": guidance,
        "summary": {"competencies": len(competencies), "indicators": total, "levels": len(LEVEL_POINTS)},
        "competencies": competencies,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    model = parse_workbook(locate_workbook(args.materials))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        fh.write("# GENERATED by scripts/import_competency_model.py – do not edit by hand.\n")
        yaml.safe_dump(model, fh, allow_unicode=True, sort_keys=False, width=120)
    print(f"Wrote {args.output} ({model['summary']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
