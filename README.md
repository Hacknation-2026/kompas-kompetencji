# Kompas Kompetencji – Backend

Backend aplikacji **Kompas Kompetencji** (HackNation 2026 – Ministerstwo Cyfryzacji, Biuro Dyrektora Generalnego) wspierającej przełożonych oraz kadry (HR) w prowadzeniu **pierwszej oceny** oraz **oceny okresowej** w służbie cywilnej w oparciu o oficjalny model kompetencyjny i asystenta AI (RAG).

## Struktura projektu

- `config/` – warstwowa konfiguracja YAML (`base.yaml`, `environments/`, `models/llm/`, `models/embeddings/`, `forms.yaml`, `scoring.yaml`, `workflows.yaml`, `prompts.yaml`).
- `data/` – model kompetencji (`data/competency_model/model_kompetencji.yaml`), baza wiedzy (`data/knowledge_base/`), fikcyjne dane testowe (`data/samples/`).
- `models/` – lokalne artefakt y AI (zbudowany indeks RAG `models/index/chunks.json`, opcjonalne wagi embeddingów).
- `docs/` – dokumentacja architektury i statusu prac (`ARCHITECTURE.md`, `STATUS.md`).
- `scripts/` – skrypty pomocnicze (`import_competency_model.py`, `build_knowledge_base.py`, `run_demo_scenario.py`, `clean.py`).
- `src/kompas/` – aplikacja FastAPI/Uvicorn w architekturze warstwowej (SOLID, DIP, rejestry komponentów).
- `tests/` – testy jednostkowe i integracyjne z bramką pokrycia (`>= 85%`).

## Szybki start

```bash
make install          # instalacja zależności (uv)
make kb               # budowa indeksu bazy wiedzy w models/index/chunks.json
make dev              # uruchomienie API (uvicorn z auto-reload) -> http://127.0.0.1:8000/api/v1/docs
make check            # lint (ruff) + typy (mypy) + testy i pokrycie (pytest-cov)
make verify           # smoke-test E2E na danych z data/samples/
```

Zmiana modelu AI odbywa się wyłącznie konfiguracją (np. `KOMPAS__LLM__PROFILE=ollama` lub `gemini`, albo `KOMPAS__RETRIEVER__PROVIDER=hybrid`).
