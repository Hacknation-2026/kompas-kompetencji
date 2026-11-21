"""Unit tests for knowledge-base ingestion (incl. PDF), Bielik/Ollama and OpenAI-compatible clients."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fpdf import FPDF

from kompas.assistant.knowledge import KnowledgeBaseBuilder, load_index, save_index
from kompas.assistant.llm import OllamaLLMClient, OpenAICompatibleLLMClient
from kompas.container import AppContainer
from kompas.core.config import load_settings
from kompas.core.exceptions import ConfigurationError, ExternalServiceError
from kompas.domain.enums import AssistantMode


def test_dev_environment_uses_bielik_and_hybrid_retriever() -> None:
    cfg = load_settings(environment="dev", environ={})
    assert cfg.llm.profile == "bielik"
    assert cfg.llm.provider == "ollama"
    assert "bielik" in cfg.llm.params["model"].lower()
    assert cfg.retriever.provider == "hybrid"


def test_knowledge_base_builder_reads_pdf_md_and_persists_index(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "note.md").write_text("Termin na sprzeciw wynosi 7 dni od zapoznania.", encoding="utf-8")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Rozporzadzenie w sprawie ocen okresowych w sluzbie cywilnej.")
    pdf.output(str(kb_dir / "sample.pdf"))

    builder = KnowledgeBaseBuilder(chunk_size=50, overlap=10)
    chunks = builder.build(kb_dir=kb_dir)
    ids = {c.id for c in chunks}
    assert "note.md#1" in ids
    assert "sample.pdf#1" in ids

    idx_path = tmp_path / "index" / "chunks.json"
    save_index(chunks, idx_path)
    reloaded = load_index(idx_path)
    assert len(reloaded) == len(chunks)
    assert reloaded[0].source == chunks[0].source


def test_ollama_bielik_client_payload_and_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, json: dict[str, object], timeout: float) -> MagicMock:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        resp = MagicMock()
        resp.json.return_value = {"message": {"content": "  Odpowiedź Bielika [1].  "}}
        return resp

    monkeypatch.setattr(httpx, "post", fake_post)
    client = OllamaLLMClient(model="SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M")
    out = client.generate("SYS", "USER")
    assert out == "Odpowiedź Bielika [1]."
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["model"] == "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M"  # type: ignore[index]

    def fail_connect(*_args: object, **_kwargs: object) -> None:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", fail_connect)
    with pytest.raises(ExternalServiceError, match="ollama pull"):
        client.generate("SYS", "USER")


def test_openai_compatible_client_and_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_LLM_KEY", raising=False)
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        model="demo-model",
        api_key_env="TEST_LLM_KEY",
    )
    with pytest.raises(ConfigurationError, match="TEST_LLM_KEY"):
        client.generate("SYS", "USER")

    monkeypatch.setenv("TEST_LLM_KEY", "secret-key")
    resp = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
    monkeypatch.setattr(httpx, "post", lambda *_a, **_kw: resp)
    assert client.generate("SYS", "USER") == "OK"


def test_assistant_retrieves_statutory_rules_from_full_kb(container: AppContainer) -> None:
    q1 = container.assistant.ask(
        "Po jakim czasie od negatywnej oceny okresowej przeprowadza się ponowną ocenę?",
        mode=AssistantMode.FORMAL,
    )
    assert q1.grounded is True
    assert any("6 miesięcy" in c.excerpt or "6 miesięcy" in q1.answer for c in q1.citations)

    q2 = container.assistant.ask(
        "W jakim terminie dyrektor generalny rozpatruje sprzeciw?",
        mode=AssistantMode.FORMAL,
    )
    assert q2.grounded is True
    assert "14 dni" in q2.answer or any("14 dni" in c.excerpt for c in q2.citations)
