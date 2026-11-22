# Status realizacji projektu – Kompas Kompetencji

| Etap | Zakres | Status |
|---|---|---|
| 1. Analiza materiałów konkursowych | Przepisy (rozp. 2015 i 2016), poradniki KPRM, `Model_kompetencji.xlsx`, szablony OSP | Zakończono |
| 2. Konfiguracja i orkiestracja | `pyproject.toml`, `Makefile`, `.pre-commit-config.yaml`, warstwowe `config/*.yaml` | Zakończono |
| 3. Warstwa domeny i danych | Encje domenowe, `model_kompetencji.yaml` (14 kompetencji, 49 wskaźników), dane testowe | Zakończono |
| 4. Silnik ocen i workflow | Ścieżki pierwszej oceny i oceny okresowej (A/B/C), terminy wg KC, strategie sugestii i polityki prawne | Zakończono |
| 5. Asystent AI (RAG) | Baza wiedzy (FAQ + przepisy + model), BM25/Embedding/Hybrid retriever, Extractive/Ollama/OpenAI LLM, guardrails | Zakończono |
| 6. Dokumenty, powiadomienia, integracje | Eksport PDF/HTML, archiwum EZD (stub), brama QNT (stub), przypomnienia HR | Zakończono |
| 7. API HTTP i testy | Routery FastAPI, RBAC, testy jednostkowe i integracyjne z pokryciem >= 85% | Zakończono |
| 8. Faza 4 – UI/UX, przypadki brzegowe i pakiet zgłoszeniowy | Pełny formularz Zał. nr 3, Część III (wniosek o stopień), dowody STAR, przedłużanie terminów, nadpisanie arkusza, ponowna ocena 6-mies., dokumentacja `DEMO_SCRIPT.md`, `SUBMISSION.md`, `PRESENTATION.md` | Zakończono |
| 9. Faza 5 – Utwardzenie produkcyjne (MC) | Repozytorium `postgres` (SQLAlchemy + Alembic) i `sqlite`, SSO (`oidc`/`saml2`), rate limiting + nagłówki bezpieczeństwa, audyt RODO + retencja + maskowanie logów, integracje `QntHrGateway` i `EzdRpArchiveGateway`, worker przypomnień | Zakończono |

