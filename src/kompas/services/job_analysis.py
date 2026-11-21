"""Job description (OSP) analysis: recommends form (B vs C) and additional criteria."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from kompas.competency.criteria import CriteriaPolicy
from kompas.domain.competency import CompetencyModel
from kompas.domain.enums import FormType


class JobAnalysisResult(BaseModel):
    recommended_form: FormType
    recommended_additional_criteria: list[dict[str, str]] = Field(default_factory=list)
    rationale: str


# Keywords mapped to competency ids (from Poradnik / Rozporządzenie descriptions).
_COMPETENCY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "myslenie_analityczne": ("analiz", "orzeczn", "danych", "wniosk", "ocen", "raport"),
    "negocjowanie": ("negocj", "porozum", "uzgodn", "kontrakt", "umów", "umow"),
    "wystapienia_publiczne": ("prezent", "wystąp", "konferenc", "szkolen", "audytor", "reprezent"),
    "orientacja_na_klienta": ("klient", "interesant", "obywatel", "wnioskodawc", "obsług"),
    "radzenie_sobie_w_kryzysie": ("kryzys", "incydent", "awari", "zagroż", "eskalac", "ryzyk"),
    "kreatywnosc": ("innowac", "nowych rozwiązań", "koncepcj", "projektow", "usprawn"),
    "zarzadzanie_strategiczne": ("strateg", "wizj", "długofalow", "polityk"),
    "podejmowanie_decyzji": ("decyzj", "rozstrzyg", "samodzieln", "odpowiedzialn"),
    "zarzadzanie_ludzmi": ("kieruj", "zespoł", "podległ", "delegow", "nadzoruj"),
}


class JobAnalysisService:
    """Analyses an OSP text (Opis Stanowiska Pracy) for periodic evaluation setup."""

    def __init__(self, model: CompetencyModel, criteria_policy: CriteriaPolicy) -> None:
        self.model = model
        self.criteria_policy = criteria_policy

    def analyze(
        self, text: str, manages_people: bool = False, is_head_of_office: bool = False
    ) -> JobAnalysisResult:
        lower = text.lower()
        if is_head_of_office:
            form = FormType.A
        elif manages_people or bool(re.search(r"kieruje\s+pracą|podległych\s+pracowników|naczelnik", lower)):
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
