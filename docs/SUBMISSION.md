# Kompas Kompetencji — Dokumentacja zgłoszeniowa (HackNation 2026)

## 1. Koncepcja i najważniejsze funkcjonalności
**Kompas Kompetencji** to aplikacja webowa wspierająca przełożonych oraz pracowników kadr (HR) w Ministerstwie Cyfryzacji w przeprowadzeniu **pierwszej oceny** (rozporządzenie z 23.07.2015 r.) oraz **oceny okresowej** (rozporządzenie z 04.04.2016 r.) w służbie cywilnej.

Kluczowe funkcjonalności prototypu:
- **Dwie kompletne ścieżki procesu (kreator krok po kroku)**:
  - *Pierwsza ocena*: rozmowa wstępna (21 dni), sprawozdanie ocenianego (Załącznik nr 3, min. 7 miesięcy), ocena 5 elementów w skali 3/5/7 pkt, rozmowa oceniająca, egzamin ze służby przygotowawczej, wynik końcowy i eksport dokumentu.
  - *Ocena okresowa*: analiza opisu stanowiska pracy (OSP w `.docx`/`.pdf`/`.txt`) z rekomendacją formularza (A/B/C) i kryteriów dodatkowych, ustalenie kryteriów (Część I, 30 dni lub 7 dni przy ponownej ocenie po ocenie negatywnej), ocena wskaźników behawioralnych w skali 1–9 pkt, rozmowa oceniająca, wynik końcowy (Część II), wniosek o kolejny stopień służbowy (Część III), pouczenie o 7-dniowym sprzeciwie.
- **Model kompetencyjny i dowody STAR**:
  - Zaimportowane z oficjalnych materiałów 14 kompetencji i 49 wskaźników behawioralnych z opisami poziomów oraz opcją *Brak podstaw*.
  - Możliwość zapisywania notatek dowodowych STAR (*Sytuacja – działanie – rezultat*) przy każdym wskaźniku.
- **Zarządzanie terminami**:
  - Automatyczne wyliczanie terminów zgodnie z Kodeksem cywilnym (art. 111–115 KC, w tym święta w Polsce) oraz obsługa przedłużania terminów w razie nieobecności (§ 5 rozp. 2015 / art. 81 ust. 8 ustawy) i ponownej oceny po 6 miesiącach (art. 81 ust. 9 ustawy).
- **Eksport dokumentacji**:
  - Generowanie arkuszy oceny w formacie **PDF** oraz **HTML** (z opcjonalną archiwizacją).
- **Panel HR / Administratora**:
  - Monitorowanie postępów, przegląd nadchodzących i zaległych terminów oraz wysyłka przypomnień do przełożonych.
- **Dostępność wyłącznie na desktop/tablet**:
  - Zgodnie z wymaganiami wyzwania interfejs blokuje dostęp na ekranach smartfonów (`< 768px`).

---

## 2. Wykorzystanie sztucznej inteligencji (AI)
AI pełni w systemie funkcję **wyłącznie doradczą i wspierającą** — nigdy nie podejmuje decyzji o ocenie pracownika:

1. **Asystent formalny (RAG)**:
   - Oparty o lokalny, otwarty model językowy **Bielik** (`SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M`, licencja Apache 2.0, uruchamiany lokalnie przez **Ollama**).
   - **Hybrydowe wyszukiwanie (HybridRetriever)**: łączy wyszukiwanie leksykalne **BM25** z gęstymi embeddingami wielojęzycznymi (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`).
   - Indeks bazy wiedzy obejmuje **277 chunków** z oficjalnych PDF-ów (ustawa o służbie cywilnej, rozporządzenia 2015 i 2016, poradniki KPRM), `faq.yaml` oraz `model_kompetencji.yaml`.
   - Każda odpowiedź zawiera jawne cytowania źródeł; przy niskiej trafności (`min_relevance`) asystent komunikuje brak wystarczających informacji zamiast halucynować.
2. **Asystent rozmowy**:
   - Generuje spersonalizowany plan rozmowy oceniającej dla aktywnej oceny (pytania otwierające, wątki dla poszczególnych kryteriów, wskazówki do IPRZ).
3. **Sugestia poziomu kompetencji (wyłącznie pomocnicza)**:
   - Strategia `MeanNearestStrategy` oblicza średnią z wybranych wskaźników behawioralnych i podpowiada najbliższy poziom na skali formularza. Ostateczną ocenę cząstkową zawsze wybiera przełożony.
4. **Zabezpieczenia (Guardrails)**:
   - `RatingDecisionGuardrail`: blokuje próby wymuszenia na asystencie wystawienia oceny za przełożonego.
   - `PersonalDataGuardrail`: maskuje dane wrażliwe (PESEL, e-mail, numer telefonu) przed przekazaniem zapytania do LLM.

---

## 3. Zastosowane technologie i architektura
- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2.
- **Architektura (SOLID & Config-Driven)**:
  - Warstwowy podział odpowiedzialności (`domain`, `competency`, `scoring`, `workflow`, `assistant`, `documents`, `notifications`, `integrations`, `persistence`, `security`, `services`, `api`).
  - Wzorzec `Registry` (`src/kompas/core/registry.py`) oraz wstrzykiwanie zależności przez `AppContainer` (`src/kompas/container.py`) — wymiana modelu LLM, embeddingów, repozytorium czy bram zewnętrznych odbywa się w plikach YAML bez modyfikacji logiki biznesowej.
- **Dokumenty**: `fpdf2` (PDF), `Jinja2` (HTML), `python-docx` / `pypdf` (analiza OSP).
- **Frontend**: lekki, responsywny interfejs SPA (HTML5 / CSS3 / Vanilla JS) serwowany bezpośrednio przez FastAPI.
- **Jakość**: `pytest` + `pytest-cov`, `ruff`, `mypy`.

---

## 4. Wymagane dostosowania przed wdrożeniem produkcyjnym w MC
1. **Trwała baza danych**: zastąpienie `json_file`/`memory` implementacją PostgreSQL (`SqlAlchemyRepository` + migracje Alembic).
2. **Tożsamość i uwierzytelnianie**: integracja z korporacyjnym SSO (OIDC / SAML2 / Active Directory / gov.pl) zamiast lokalnych kont demo.
3. **Utwardzenie API i prywatności**: rate limiting na `/auth/login` i `/assistant/ask`, ścisłe reguły CORS, terminacja TLS za reverse proxy, zarządzanie sekretami (Vault/env), eksport niemodyfikowalnych logów audytowych RODO oraz automatyczna retencja/anonimizacja danych.
4. **Integracje z systemami administracji**:
   - System kadrowy **QNT** (`QntHrGateway`) do synchronizacji struktury organizacyjnej, podległości i statusu mianowania.
   - System zarządzania dokumentacją **EZD RP / EZD PUW** (`EzdRpArchiveGateway`) do automatycznego przekazywania podpisanych arkuszy do akt osobowych.
5. **Harmonogram przypomnień**: uruchomienie cyklicznego workera dla `MonitoringService.send_reminders()` przez SMTP z TLS.
