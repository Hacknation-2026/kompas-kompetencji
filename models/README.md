# `models/` – AI Model Files & Indexes

This directory holds local AI artefacts (kept out of git by `.gitignore`):

| Subdirectory | Contents | How to populate |
|---|---|---|
| `models/index/` | Chunked RAG corpus (`chunks.json`) | `make kb` |
| `models/embeddings/` | Cached `sentence-transformers` weights | Automatic on first run with `embeddings.profile=sentence_transformers` (`make install-ml`) |
| `models/llm/` | Optional local GGUF/weights if serving offline models | Managed by Ollama or local inference server |

The default configuration (`config/models/llm/extractive.yaml` + `config/models/embeddings/hashing.yaml`)
requires **no downloaded weights** and runs deterministically offline.

