# Architektura backendu – Kompas Kompetencji

## 1. Założenia (SOLID & Config-Driven)
System został zaprojektowany w architekturze warstwowej z odwróceniem zależności (DIP):

- **Single Responsibility (SRP)**: każdy pakiet odpowiada za jeden obszar (model kompetencji, punktacja, workflow, RAG/AI, dokumenty, powiadomienia, integracje, bezpieczeństwo).
- **Open/Closed (OCP)**: każdy wymienny komponent ma własny `Registry` (`src/kompas/core/registry.py`) i jest wybierany w YAML (`provider` + `params`). Dodanie nowego modelu LLM, backendu embeddingów, repozytorium SQL czy integracji EZD/QNT nie wymaga modyfikacji istniejących klas.
- **Liskov Substitution (LSP)**: wszystkie implementacje dziedziczą po klasach bazowych ABC (`Repository`, `LLMClient`, `EmbeddingModel`, `Retriever`, `OutcomePolicy`, `IndicatorAggregationStrategy`, `DocumentRenderer`, `Notifier`, `HRGateway`, `ArchiveGateway`).
- **Interface Segregation (ISP)** i **Dependency Inversion (DIP)**: serwisy w `kompas.services` zależą wyłącznie od abstrakcji wstrzykiwanych przez `AppContainer` (`src/kompas/container.py`).

## 2. Struktura katalogów
- `config/` – warstwowa konfiguracja YAML (`base.yaml`, `environments/*.yaml`, `models/llm/*.yaml`, `models/embeddings/*.yaml`, `forms.yaml`, `scoring.yaml`, `workflows.yaml`, `prompts.yaml`).
- `data/` – model kompetencji (`data/competency_model/model_kompetencji.yaml`), baza wiedzy RAG (`data/knowledge_base/`), fikcyjne dane testowe (`data/samples/`).
- `models/` – lokalne artefakty AI (indeks chunków RAG, opcjonalne wagi embeddingów).
- `src/kompas/` – główna aplikacja FastAPI + Uvicorn.
- `scripts/` – import danych z materiałów konkursowych, budowa indeksu wiedzy, smoke-test E2E.
- `tests/` – testy jednostkowe i integracyjne z pomiarem pokrycia (`pytest-cov`).

## 3. Bezpieczeństwo i zgodność z wymaganiami AI
- Uwierzytelnianie JWT (`HS256`) + hashowanie haseł PBKDF2-HMAC-SHA256 + kontrola dostępu RBAC (`supervisor`, `hr`, `admin`).
- Asystent AI jest **wyłącznie doradczy**: `RatingDecisionGuardrail` blokuje próby wymuszenia decyzji o ocenie, a `PersonalDataGuardrail` maskuje PESEL/e-mail/telefon przed wysłaniem zapytania do LLM.
- Przy niskiej trafności źródeł (`min_relevance`) asystent komunikuje brak wystarczających informacji w bazie wiedzy zamiast halucynować.

