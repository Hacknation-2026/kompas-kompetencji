"""Build the RAG knowledge base index from data/knowledge_base, FAQ, competency model and optional PDFs."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from kompas.assistant.knowledge import KnowledgeBaseBuilder, save_index
from kompas.competency.loader import YamlCompetencyModelLoader
from kompas.core.config import get_settings


def extract_pdfs_from_materials(materials: Path, target_dir: Path) -> int:
    """Optionally unpack legal PDFs from HackNation.zip into ``target_dir``."""
    if not materials.exists():
        return 0
    extracted = 0
    target_dir.mkdir(parents=True, exist_ok=True)
    for archive in materials.rglob("*.zip"):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if not member.lower().endswith(".pdf"):
                    continue
                dest = target_dir / Path(member).name
                if not dest.exists():
                    dest.write_bytes(zf.read(member))
                    extracted += 1
    return extracted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials", type=Path, default=None, help="Optional folder with HackNation.zip")
    parser.add_argument(
        "--include-pdfs", action="store_true", help="Unpack PDFs from --materials before indexing"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.include_pdfs and args.materials is not None:
        count = extract_pdfs_from_materials(args.materials, settings.assistant.knowledge_base_dir / "pdfs")
        print(f"Extracted {count} PDFs")

    model = YamlCompetencyModelLoader(settings.paths.competency_model_file).load()
    builder = KnowledgeBaseBuilder(
        chunk_size=settings.assistant.chunk_size,
        overlap=settings.assistant.chunk_overlap,
    )
    chunks = builder.build(
        kb_dir=settings.assistant.knowledge_base_dir,
        faq_file=settings.assistant.faq_file,
        model=model,
    )
    index_file = settings.assistant.index_file or (settings.paths.models_dir / "index" / "chunks.json")
    save_index(chunks, index_file)
    print(f"Saved {len(chunks)} chunks -> {index_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
