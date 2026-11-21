"""Knowledge-base ingestion, chunking and index persistence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from kompas.domain.competency import CompetencyModel


class KnowledgeChunk(BaseModel):
    """Single citable fragment in the knowledge base."""

    id: str
    source: str
    title: str
    section: str | None = None
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def chunk_text(text: str, chunk_size: int = 180, overlap: int = 40) -> list[str]:
    """Split text into overlapping word windows."""
    words = re.split(r"\s+", text.strip())
    words = [w for w in words if w]
    if not words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words)]
    step = max(1, chunk_size - overlap)
    chunks: list[str] = []
    for start in range(0, len(words), step):
        window = words[start : start + chunk_size]
        chunks.append(" ".join(window))
        if start + chunk_size >= len(words):
            break
    return chunks


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    raw = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    # Rejoin Polish words broken across PDF line-wraps and collapse whitespace.
    raw = re.sub(r"-\s*\n\s*", "", raw)
    return re.sub(r"\s+", " ", raw).strip()


class KnowledgeBaseBuilder:
    """Collects chunks from markdown/txt/pdf files, FAQ YAML and the competency model."""

    def __init__(self, chunk_size: int = 180, overlap: int = 40) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def from_directory(self, directory: Path) -> list[KnowledgeChunk]:
        if not directory.is_dir():
            return []
        chunks: list[KnowledgeChunk] = []
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".pdf"}:
                continue
            raw = _read_pdf(path) if path.suffix.lower() == ".pdf" else path.read_text(encoding="utf-8")
            rel = path.relative_to(directory).as_posix()
            title = path.stem.replace("_", " ")
            for idx, piece in enumerate(chunk_text(raw, self.chunk_size, self.overlap), start=1):
                chunks.append(
                    KnowledgeChunk(
                        id=f"{rel}#{idx}",
                        source=rel,
                        title=title,
                        text=piece,
                    )
                )
        return chunks

    @staticmethod
    def from_faq(path: Path) -> list[KnowledgeChunk]:
        if not path.is_file():
            return []
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        chunks: list[KnowledgeChunk] = []
        for idx, item in enumerate(raw.get("faq", []), start=1):
            question = str(item.get("question", "")).strip()
            answer = str(item.get("answer", "")).strip()
            source = str(item.get("source", "FAQ KPRM / MC"))
            if not question or not answer:
                continue
            chunks.append(
                KnowledgeChunk(
                    id=f"faq#{idx}",
                    source=source,
                    title=question,
                    section=item.get("topic"),
                    text=f"Pytanie: {question}\nOdpowiedź: {answer}",
                )
            )
        return chunks

    @staticmethod
    def from_competency_model(model: CompetencyModel) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for comp in model.competencies:
            lines = [f"Kompetencja: {comp.name} ({comp.id})."]
            for ind in comp.indicators:
                levels = "; ".join(f"{pts} pkt: {desc}" for pts, desc in sorted(ind.levels.items()))
                lines.append(f"Wskaźnik „{ind.name}”: {levels}")
            chunks.append(
                KnowledgeChunk(
                    id=f"model#{comp.id}",
                    source="Model kompetencji w służbie cywilnej",
                    title=comp.name,
                    text="\n".join(lines),
                )
            )
        return chunks

    def build(
        self,
        kb_dir: Path,
        faq_file: Path | None = None,
        model: CompetencyModel | None = None,
    ) -> list[KnowledgeChunk]:
        chunks = self.from_directory(kb_dir)
        if faq_file is not None:
            chunks.extend(self.from_faq(faq_file))
        if model is not None:
            chunks.extend(self.from_competency_model(model))
        return chunks


def save_index(chunks: list[KnowledgeChunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [c.model_dump(mode="json") for c in chunks]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_index(path: Path) -> list[KnowledgeChunk]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8") or "[]")
    return [KnowledgeChunk.model_validate(item) for item in raw]
