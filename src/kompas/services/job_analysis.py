"""Job description (OSP) analysis: recommends form (B vs C) and additional criteria."""

from __future__ import annotations

import io
import re
from pathlib import Path

from pydantic import BaseModel, Field

from kompas.competency.criteria import CriteriaPolicy
from kompas.core.exceptions import ValidationError
from kompas.domain.competency import CompetencyModel
from kompas.domain.enums import FormType


class JobAnalysisResult(BaseModel):
    recommended_form: FormType
    recommended_additional_criteria: list[dict[str, str]] = Field(default_factory=list)
    rationale: str


# Keywords mapped to competency ids (calibrated against official MC OSP templates & Poradnik).
_COMPETENCY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "myslenie_analityczne": ("myślenie analityczne", "analiz", "orzeczn", "danych", "wniosk", "raport"),
    "negocjowanie": ("negocj", "porozum", "uzgodn", "przekonyw", "godzenie interesów", "kontrakt"),
    "wystapienia_publiczne": ("wystąpie", "prezent", "konferenc", "szkolen", "audytor", "reprezent"),
    "orientacja_na_klienta": ("klient", "interesant", "obywatel", "wnioskodawc", "obsług"),
    "radzenie_sobie_w_kryzysie": (
        "zarządzania kryzysowego",
        "kryzys",
        "incydent",
        "awari",
        "zagroż",
        "eskalac",
    ),
    "kreatywnosc": ("kreatywn", "innowac", "nowych rozwiązań", "koncepcj", "projektow", "usprawn"),
    "zarzadzanie_strategiczne": ("zarządzanie strategiczne", "strateg", "wizj", "długofalow", "polityk"),
    "podejmowanie_decyzji": ("podejmowanie decyzji", "decyzj", "rozstrzyg", "samodzieln", "odpowiedzialn"),
    "zarzadzanie_ludzmi": ("zarządzanie ludźmi", "kieruj", "zespoł", "podległ", "delegow", "nadzoruj"),
    "wykorzystywanie_wiedzy": ("wykorzystywanie wiedzy", "doskonalenie zawodowe", "wiedzy eksperckiej"),
    "rzetelnosc": ("rzeteln", "jakość", "procedur", "terminow", "kontrol"),
}

_MANAGER_PATTERN = re.compile(
    r"kieruje\s+pracą|bezpośredniego\s+przełożonego|zarządzając\s+zespołem|"
    r"ocena\s+pracy\s+podległych|naczelnik\s+wydziału|kieruje\s+zespołem",
)


class JobAnalysisService:
    """Analyses an OSP text or uploaded .docx/.pdf file for periodic evaluation setup."""

    def __init__(self, model: CompetencyModel, criteria_policy: CriteriaPolicy) -> None:
        self.model = model
        self.criteria_policy = criteria_policy

    @staticmethod
    def extract_text_from_file(filename: str, content: bytes) -> tuple[str, bool | None]:
        """Extract text (and optional Word checkbox managerial flag) from .docx/.pdf/.txt."""
        suffix = Path(filename).suffix.lower()
        if suffix in {".txt", ".md"}:
            return content.decode("utf-8", errors="replace"), None
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text, None
        if suffix == ".docx":
            import docx

            doc = docx.Document(io.BytesIO(content))
            parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            manages_flag: bool | None = None
            for table in doc.tables:
                for row in table.rows:
                    row_text = " ".join(c.text.strip() for c in row.cells if c.text.strip())
                    if row_text:
                        parts.append(row_text)
                    xml = row._tr.xml
                    if "podległych" in row_text.lower() or "kieruje lub koordynuje" in row_text.lower():
                        # Checked Word form/content-control checkbox near subordinate count
                        has_checked = 'w:val="1"' in xml or "<w14:checked/>" in xml or "☒" in row_text
                        if has_checked and "brak podległych" not in row_text.lower():
                            manages_flag = True
            return "\n".join(parts), manages_flag
        raise ValidationError(
            f"Nieobsługiwany format pliku OSP '{suffix}'. Dozwolone: .docx, .pdf, .txt, .md"
        )

    def analyze_file(
        self,
        filename: str,
        content: bytes,
        manages_people: bool | None = None,
        is_head_of_office: bool = False,
    ) -> JobAnalysisResult:
        text, detected_manages = self.extract_text_from_file(filename, content)
        effective_manages = detected_manages if manages_people is None else manages_people
        return self.analyze(
            text=text,
            manages_people=bool(effective_manages),
            is_head_of_office=is_head_of_office,
        )

    def analyze(
        self, text: str, manages_people: bool = False, is_head_of_office: bool = False
    ) -> JobAnalysisResult:
        lower = text.lower()
        if is_head_of_office:
            form = FormType.A
        elif manages_people or bool(_MANAGER_PATTERN.search(lower)):
            form = FormType.B
        else:
            form = FormType.C

        allowed = set(self.criteria_policy.allowed_additional(form))
        scored: list[tuple[int, str, list[str]]] = []
        for cid in allowed:
            keywords = _COMPETENCY_KEYWORDS.get(cid, ())
            matched = [kw for kw in keywords if kw in lower]
            if matched:
                scored.append((len(matched), cid, matched))
        scored.sort(key=lambda item: item[0], reverse=True)

        max_add = self.criteria_policy.form(form).max_additional_criteria
        recommendations = [
            {
                "competency_id": cid,
                "name": self.model.get(cid).name,
                "reason": f"Słowa kluczowe w OSP: {', '.join(matched)}",
            }
            for _, cid, matched in scored[:max_add]
        ]
        kind = "stanowisko kierownicze" if form in (FormType.A, FormType.B) else "stanowisko niekierownicze"
        rationale = f"Rekomendowany formularz {form.value} ({kind})."
        return JobAnalysisResult(
            recommended_form=form,
            recommended_additional_criteria=recommendations,
            rationale=rationale,
        )
