"""Pluggable document renderers (PDF via fpdf2, HTML via Jinja2)."""

from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from fpdf import FPDF
from jinja2 import Template

from kompas.core.registry import Registry
from kompas.documents.builder import EvaluationDocumentData

_HTML_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8" />
<title>{{ doc.form_title }} – {{ doc.employee_name }}</title>
<style>
  body { font-family: Arial, sans-serif; margin: 32px; color: #1b2430; line-height: 1.45; }
  h1 { font-size: 20px; margin-bottom: 4px; }
  .meta { color: #52606d; font-size: 13px; margin-bottom: 18px; }
  table { width: 100%; border-collapse: collapse; margin: 14px 0; }
  th, td { border: 1px solid #cbd2d9; padding: 8px; text-align: left; font-size: 13px; }
  th { background: #f0f4f8; }
  .badge-pos { color: #0e6027; font-weight: bold; }
  .badge-neg { color: #a2191f; font-weight: bold; }
</style>
</head>
<body>
  <h1>{{ doc.form_title }}</h1>
  <div class="meta">{{ doc.office_name }} | {{ doc.legal_basis }} | ID: {{ doc.evaluation_id }}</div>

  <h2>1. Dane podstawowe</h2>
  <table>
    <tr>
      <th>Oceniany</th>
      <td>{{ doc.employee_name }} ({{ doc.employee_position }}, {{ doc.employee_org_unit }})</td>
    </tr>
    <tr><th>Oceniający</th><td>{{ doc.evaluator_name }} ({{ doc.evaluator_position }})</td></tr>
  </table>

  <h2>2. Kryteria i oceny cząstkowe</h2>
  <table>
    <tr><th>Kryterium</th><th>Rodzaj</th><th>Sugestia systemu</th><th>Ocena ostateczna</th></tr>
    {% for r in doc.criteria_rows %}
    <tr>
      <td>{{ r.name }}</td>
      <td>{{ r.kind }}</td>
      <td>{{ r.suggested_points if r.suggested_points is not none else "-" }}</td>
      <td>{{ r.final_points if r.final_points is not none else "-" }} ({{ r.final_label }})</td>
    </tr>
    {% endfor %}
  </table>

  {% if doc.positive is not none %}
  <h2>3. Wynik oceny</h2>
  <p>Średnia: <strong>{{ doc.average }}</strong>
     {% if doc.overall_label %} ({{ doc.overall_label }}){% endif %} –
     <span class="{{ 'badge-pos' if doc.positive else 'badge-neg' }}">
       {{ 'OCENA POZYTYWNA' if doc.positive else 'OCENA NEGATYWNA' }}
     </span>
  </p>
  {% endif %}

  {% if doc.justification %}
  <h3>Uzasadnienie oceny</h3>
  <p>{{ doc.justification }}</p>
  {% endif %}

  {% if doc.development_plan %}
  <h3>Wnioski rozwojowe (IPRZ)</h3>
  <p>{{ doc.development_plan }}</p>
  {% endif %}
</body>
</html>"""
)


class DocumentRenderer(ABC):
    """Renders :class:`EvaluationDocumentData` to bytes."""

    media_type: str = "application/octet-stream"
    extension: str = "bin"

    @abstractmethod
    def render(self, data: EvaluationDocumentData) -> bytes: ...


renderer_registry: Registry[DocumentRenderer] = Registry("documents")


@renderer_registry.register("html")
class HtmlRenderer(DocumentRenderer):
    media_type = "text/html; charset=utf-8"
    extension = "html"

    def render(self, data: EvaluationDocumentData) -> bytes:
        return _HTML_TEMPLATE.render(doc=data).encode("utf-8")


@renderer_registry.register("pdf")
class PdfRenderer(DocumentRenderer):
    media_type = "application/pdf"
    extension = "pdf"

    def __init__(self, font_candidates: Sequence[str] = ()) -> None:
        self.font_path = self._find_font(font_candidates)

    @staticmethod
    def _find_font(candidates: Sequence[str]) -> Path | None:
        for candidate in candidates:
            path = Path(candidate)
            if path.is_file():
                return path
        return None

    def _safe(self, text: str) -> str:
        if self.font_path is not None:
            return text
        normalized = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
        return normalized.encode("latin-1", "ignore").decode("latin-1")

    def render(self, data: EvaluationDocumentData) -> bytes:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        if self.font_path is not None:
            pdf.add_font("CustomSans", "", str(self.font_path))
            font_family = "CustomSans"
        else:
            font_family = "Helvetica"

        def write_line(text: str, size: int = 10, height: int = 6) -> None:
            pdf.set_font(font_family, size=size)
            pdf.multi_cell(0, height, self._safe(text), new_x="LMARGIN", new_y="NEXT")

        write_line(data.form_title, size=14, height=8)
        write_line(f"{data.office_name} | {data.legal_basis}", size=9, height=5)
        pdf.ln(3)
        write_line(f"Oceniany: {data.employee_name} ({data.employee_position}, {data.employee_org_unit})")
        write_line(f"Oceniający: {data.evaluator_name} ({data.evaluator_position})")
        pdf.ln(3)
        write_line("Kryteria i oceny cząstkowe:", size=11, height=7)
        for row in data.criteria_rows:
            pts = str(row.final_points) if row.final_points is not None else "-"
            sug = str(row.suggested_points) if row.suggested_points is not None else "-"
            write_line(f"- {row.name} [{row.kind}]: ocena {pts} ({row.final_label}), sugestia: {sug}")
        if data.positive is not None:
            pdf.ln(2)
            verdict = "POZYTYWNA" if data.positive else "NEGATYWNA"
            overall = f" ({data.overall_label})" if data.overall_label else ""
            write_line(f"Wynik oceny: {verdict} | średnia: {data.average}{overall}", size=11, height=7)
        if data.exam_status:
            write_line(f"Egzamin ze służby przygotowawczej: {data.exam_status}")
        if data.report_status:
            write_line(f"Sprawozdanie ocenianego: {data.report_status}")
        if data.justification:
            pdf.ln(2)
            write_line(f"Uzasadnienie: {data.justification}")
        if data.development_plan:
            pdf.ln(2)
            write_line(f"Wnioski rozwojowe (IPRZ): {data.development_plan}")

        return bytes(pdf.output())
