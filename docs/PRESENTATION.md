# Kompas Kompetencji — Prezentacja projektu (10 slajdów, HackNation 2026)

> Wersja interaktywna do wyświetlenia przed jury oraz eksportu do PDF (16:9): **`docs/prezentacja.html`**  
> Skróty klawiszowe w prezentacji: `←` / `→` / `Spacja` (nawigacja), `F` (pełny ekran), `N` (notatki prezentera), `G` (siatka slajdów), `Ctrl+P` (zapis jako PDF).

---

## Slajd 1: Kompas Kompetencji — System wsparcia ocen pracowniczych w służbie cywilnej
- **Wyzwanie**: Ministerstwo Cyfryzacji — Biuro Dyrektora Generalnego (HackNation 2026).
- **Wartość**: Jedno spójne narzędzie prowadzące przełożonego krok po kroku przez **proces formalny**, **model kompetencyjny** i **rozmowę oceniającą** — z lokalnym asystentem AI (Bielik + RAG), który doradza, ale **nigdy nie zastępuje decyzji człowieka**.
- **Filar 1**: Pierwsza ocena (2015) & Ocena okresowa (2016) · **Filar 2**: 14 kompetencji / 49 wskaźników · **Filar 3**: Lokalny Bielik 11B (Apache 2.0) · **Filar 4**: Eksport PDF + Panel HR.

---

## Slajd 2: Problem — Rozproszone przepisy i subiektywność oceny
- **Ryzyko formalne**: Przełożony musi jednocześnie stosować ustawę o służbie cywilnej, 2 rozporządzenia (2015 i 2016), poradniki KPRM i reguły terminów z KC (art. 111–115). Błąd w arkuszu (A/B/C) lub terminie (21/30 dni) grozi sprzeciwem.
- **Subiektywność**: Trudność przełożenia szerokich kompetencji (np. *Komunikacja*, *Myślenie analityczne*) na 49 wskaźników behawioralnych i sprawiedliwą skalę punktową.
- **Rozmowa i HR**: Brak wsparcia w merytorycznym przygotowaniu rozmowy (IPRZ) oraz brak jednego narzędzia HR do kontroli terminów i przypomnień.
- **Nasza odpowiedź**: Jedno narzędzie zamiast 5 PDF-ów i rozproszonych arkuszy — od analizy OSP po gotowy PDF.

---

## Slajd 3: Rozwiązanie — Dwie kompletne ścieżki zgodne z rozporządzeniami
1. **Ścieżka 1: Pierwsza ocena** (*rozp. PRM z 23.07.2015 r.*, skala **3 / 5 / 7 pkt**)
   - Rozmowa wstępna (**21 dni**) → Sprawozdanie ocenianego (Zał. nr 3, **≥ 7 mies.**) → Ocena 5 elementów kompetencyjnych (+ STAR) → Rozmowa oceniająca, egzamin ze służby przygotowawczej i wynik → Zapoznanie i PDF.
2. **Ścieżka 2: Ocena okresowa** (*rozp. PRM z 04.04.2016 r.*, arkusze **A / B / C**, skala **1–9 pkt**)
   - Analiza OSP (`.docx`/`.pdf`) → Dobór arkusza A/B/C i kryteriów (**30 dni** lub **7 dni** przy ponownej ocenie po 6 mies. — art. 81 ust. 9) → Ocena wskaźników + STAR → Rozmowa → Wynik (Cz. II), Wniosek o kolejny stopień (Cz. III) i Pouczenie (**7 dni** na sprzeciw) → PDF.
- **Silnik terminów (art. 111–115 KC)**: kalendarz świąt w Polsce oraz przedłużenia przy nieobecnościach (§ 5 rozp. 2015 / art. 81 ust. 8 ustawy).

---

## Slajd 4: Doświadczenie użytkownika (UX) — Perspektywa Przełożonego i HR
- **Przełożony (`supervisor`)**:
  - Kreator krok po kroku z paskiem postępu i walidacją wymogów prawnych przed przejściem dalej.
  - Upload pliku OSP (`.docx`/`.pdf`), okno terminów i przedłużeń w nagłówku, panel boczny AI (Formalny + Rozmowa), eksport **PDF / HTML**.
- **Kadry / Administrator (`hr` / `admin`)**:
  - Dashboard postępów ocen w urzędzie, alerty nadchodzących i zaległych terminów, ręczna i cykliczna wysyłka przypomnień.
- **Zgodność z ergonomią MC**: interfejs **Desktop & Tablet** ze świadomą blokadą smartfonów (`< 768px`).

---

## Slajd 5: Model kompetencyjny i pomocnicza sugestia poziomu (Human-in-the-Loop)
- **14 kompetencji** i **49 wskaźników behawioralnych** zaimportowanych bezpośrednio z oficjalnego arkusza MC.
- **Krok A (Obserwacja)**: wybór obserwowalnego zachowania (+ opcja *Brak podstaw*) oraz opcjonalny dowód **STAR** (*Sytuacja – Działanie – Rezultat*).
- **Krok B (Sugestia)**: `MeanNearestStrategy` (min. pokrycie `50%`, konserwatywny `tie_break: lower`) oblicza sugerowany poziom na skali formularza.
- **Krok C (Decyzja)**: sugestia jest **wyłącznie pomocnicza** — ostateczną ocenę cząstkową zawsze jawnie zatwierdza lub koryguje przełożony.

---

## Slajd 6: Lokalny Asystent AI — polski Bielik 11B + Hybrid RAG
- **Suwerenność danych**: lokalny model open-source **Bielik 11B** (`SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M`, **Apache 2.0**) uruchamiany przez **Ollama** — zero transferu danych poza urząd, 0 zł kosztów licencyjnych.
- **HybridRetriever**: połączenie **BM25** (`0.65` — precyzja numerów artykułów/paragrafów) + **multilingual embeddings** (`paraphrase-multilingual-MiniLM-L12-v2`) nad **277 chunkami** (ustawa, 2 rozporządzenia, poradniki KPRM, FAQ, model kompetencji).
- **Dwa tryby pracy**:
  - *Asystent formalny*: odpowiedzi wyłącznie ze źródeł z cytowaniami; poniżej `min_relevance: 0.35` odmowa bez halucynacji.
  - *Asystent rozmowy*: spersonalizowany plan rozmowy oceniającej (pytania otwierające, argumentacja, wskazówki do IPRZ).

---

## Slajd 7: Bezpieczeństwo AI (Guardrails) i deterministyczne reguły prawa
- **`RatingDecisionGuardrail`**: blokuje próby zlecenia AI wystawienia oceny pracownikowi i przypomina o wyłącznej odpowiedzialności przełożonego.
- **`PersonalDataGuardrail`**: automatycznie maskuje `PESEL`, `e-mail` i `telefon` **przed** wysłaniem zapytania do LLM oraz w logach aplikacji.
- **Deterministyczne reguły prawa (`scoring/policies.py`)**: cząstkowa `1 pkt` wymusza wynik negatywny (§ 11 rozp. 2016), brak zdanego egzaminu blokuje pozytywną pierwszą ocenę, ocena negatywna wymaga uzasadnienia.

---

## Slajd 8: Architektura warstwowa (SOLID & Config-Driven) i Jakość Kodu
- **Warstwy**: Web SPA (Desktop/Tablet) → FastAPI + Pydantic v2 + RBAC → Serwisy (`AppContainer` DI) → Silniki domenowe (`workflow`, `scoring`, `competency`, `assistant`, `documents`) → Adaptery w `Registry` (YAML).
- **Zero Vendor Lock-in (OCP/DIP)**: zmiana modelu AI, retrievera czy bazy danych to 1 linia w `config/*.yaml` lub zmiennej środowiskowej (`KOMPAS__LLM__PROFILE=bielik`).
- **Jakość**: **39 testów** (9 plików unit + integracyjne E2E), bramka pokrycia `≥ 85%` (`pytest-cov`), `mypy` (typowanie), `ruff` (lint), `Dockerfile`, migracje `Alembic`.

---

## Slajd 9: Gotowość produkcyjna i integracje urzędowe (Faza 5 już w kodzie)
- **Trwałość i bezpieczeństwo**: `SqlAlchemyRepository` (`postgres` / `sqlite`) + migracja Alembic `001_initial_schema.py`; JWT + RBAC + adaptery **SSO (`OIDC` / `SAML2`)**; rate limiting; nagłówki bezpieczeństwa; audyt RODO i polityka retencji.
- **Kontrakty integracyjne administracji**:
  - **`QntHrGateway`**: synchronizacja struktury organizacyjnej, podległości, umów i statusu mianowania z **QNT**.
  - **`EzdRpArchiveGateway`**: automatyczne przekazywanie arkuszy PDF i metadanych do akt osobowych w **EZD RP / EZD PUW**.
  - **`worker.py` (SMTP TLS)**: cykliczna wysyłka przypomnień o terminach.

---

## Slajd 10: Plan wdrożenia w MC, skalowanie i Demo na żywo
1. **Etap 1 (Tygodnie 1–4) — Infrastruktura i audyt w MC**: wdrożenie PostgreSQL + TLS + Vault, podpięcie SSO (AD / gov.pl), serwer GPU dla Bielik 11B, testy bezpieczeństwa i WCAG.
2. **Etap 2 (Miesiące 2–3) — Integracje i pilotaż w BDG MC**: podłączenie produkcyjnych API **QNT** i **EZD RP**, worker SMTP TLS, pilotaż z przełożonymi i HR.
3. **Etap 3 (Miesiące 4+) — Skalowanie na służbę cywilną**: udostępnienie kolejnym urzędom administracji rządowej (Config-Driven YAML), analityka luk kompetencyjnych i moduł realizacji IPRZ.
- **Zapraszamy na 5-minutowe Demo na żywo + Q&A z Bielikiem!**
