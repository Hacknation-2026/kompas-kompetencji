# Kompas Kompetencji — Prezentacja projektu (10 slajdów)

---

## Slajd 1: Kompas Kompetencji
- **Wsparcie przełożonych i HR w ocenianiu pracowników służby cywilnej**
- Wyzwanie: Ministerstwo Cyfryzacji — Biuro Dyrektora Generalnego (HackNation 2026)
- Jedno spójne narzędzie łączące: **proces formalny + model kompetencji + AI (RAG)**

---

## Slajd 2: Problem — rozproszone przepisy i subiektywność oceny
- Przełożony musi jednocześnie stosować **ustawę o służbie cywilnej**, **2 rozporządzenia (2015 i 2016)**, **poradniki KPRM** oraz **model kompetencji (14 kompetencji, 49 wskaźników)**.
- Brak jednego narzędzia prowadzącego krok po kroku powoduje ryzyko błędów formalnych (terminy, wybór arkusza A/B/C) oraz niespójnych interpretacji zachowań.
- Rozmowy oceniające wymagają merytorycznego przygotowania, a HR potrzebuje bieżącego monitoringu terminów.

---

## Slajd 3: Rozwiązanie — dwie kompletne ścieżki procesu
1. **Ścieżka 1: Pierwsza ocena** (rozp. z 23.07.2015 r.)
   - Rozmowa wstępna (21 dni) → Sprawozdanie ocenianego (Zał. nr 3, ≥ 7 mies.) → Ocena 5 elementów (3/5/7 pkt) → Rozmowa → Egzamin i decyzja → Zapoznanie.
2. **Ścieżka 2: Ocena okresowa** (rozp. z 04.04.2016 r.)
   - Analiza OSP (`.docx`/`.pdf`) → Dobór arkusza A/B/C i kryteriów (30 dni lub 7 dni przy ponownej ocenie) → Ocena wskaźników (1–9 pkt) → Rozmowa → Wynik (Część II) i wniosek o stopień (Część III) → Pouczenie (7 dni na sprzeciw).

---

## Slajd 4: Demo działającego prototypu (Przełożony + HR)
- Interfejs webowy desktop/tablet (blokada smartfonów `< 768px` zgodnie z wymogiem).
- Kreator krok po kroku z walidacją wymogów prawnych przed przejściem dalej.
- Wgranie pliku OSP, przedłużanie terminów (§ 5 / art. 81 ust. 8), eksport gotowego arkusza **PDF/HTML**.
- Dedykowany **Panel HR** z wykazem terminów i wysyłką przypomnień.

---

## Slajd 5: Model kompetencyjny i pomocnicza sugestia poziomu
- Wszystkie **14 kompetencji i 49 wskaźników behawioralnych** zaimportowane z oficjalnego arkusza MC.
- Ocena poprzez wybór **konkretnego, obserwowalnego zachowania** (+ opcja *Brak podstaw* oraz dowód **STAR**).
- System oblicza **sugerowany poziom** (`MeanNearestStrategy`), ale **ostateczną ocenę cząstkową zawsze wybiera przełożony**.

---

## Slajd 6: Lokalny, ugruntowany Asystent AI (Bielik + RAG)
- Polski model open-source **Bielik 11B** (`Apache 2.0`) działający lokalnie przez Ollama — pełna suwerenność danych.
- **HybridRetriever** (BM25 + `paraphrase-multilingual-MiniLM-L12-v2`) przeszukuje 277 chunków z ustaw, rozporządzeń, poradników KPRM, FAQ i modelu kompetencji.
- **Dwa tryby wsparcia**:
  - *Asystent formalny*: odpowiedzi wyłącznie na podstawie źródeł z cytowaniami i odmową przy braku danych.
  - *Asystent rozmowy*: generowanie pytań otwierających i argumentacji do rozmowy oceniającej.

---

## Slajd 7: Bezpieczeństwo AI i zgodność prawna (Guardrails)
- **RatingDecisionGuardrail**: blokuje próby zlecenia AI podjęcia decyzji o ocenie pracownika.
- **PersonalDataGuardrail**: automatycznie maskuje PESEL, e-mail i telefon przed wysłaniem promptu do LLM.
- **Zasady prawne w kodzie**: kalendarz świąt i reguły KC (art. 111–115), blokada pozytywnej oceny przy cząstkowej 1 pkt lub niezaliczonym egzaminie, obowiązkowe uzasadnienie oceny negatywnej.

---

## Slajd 8: Architektura (SOLID & Config-Driven)
- **Python / FastAPI / Pydantic v2** z czystym podziałem warstw (`domain`, `workflow`, `scoring`, `assistant`, `services`, `api`).
- **Open/Closed & DIP**: każdy komponent (LLM, embeddingi, repozytorium, dokumenty, HR, EZD) rejestrowany w `Registry` i sterowany plikami YAML.
- Testy jednostkowe i integracyjne (`pytest-cov`), kontrola typów (`mypy`) i jakości (`ruff`).

---

## Slajd 9: Gotowość do integracji (EZD RP, QNT, SSO)
- Zdefiniowane abstrakcje `HRGateway` (QNT), `ArchiveGateway` (EZD RP) i `Repository` (PostgreSQL).
- Uwierzytelnianie JWT + RBAC (`supervisor`, `hr`, `admin`) gotowe do podpięcia pod OIDC/SAML2 (gov.pl / AD).
- Minimalizacja danych osobowych i pełny ślad audytowy zmian kroków oraz terminów.

---

## Slajd 10: Plan wdrożenia w Ministerstwie Cyfryzacji
1. **Faza produkcyjna bazy i bezpieczeństwa**: PostgreSQL + Alembic, SSO (OIDC/SAML2), rate limiting, audyt RODO.
2. **Integracje urzędowe**: synchronizacja struktury z **QNT**, archiwizacja arkuszy w **EZD RP**, cykliczne powiadomienia SMTP TLS.
3. **Pilotaż w BDG MC** → skalowanie na kolejne urzędy administracji rządowej.
