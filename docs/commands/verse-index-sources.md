# verse-index-sources

Index Puranic source texts (PDFs, TXTs, MDs) into structured episodes and embeddings for RAG retrieval.

## Synopsis

```bash
verse-index-sources --file PATH [OPTIONS]
```

## Description

`verse-index-sources` processes a source document, extracts structured Puranic episodes using GPT-4o, embeds them with the chosen provider, and writes the results to the project's data directory. The indexed episodes are later used by `verse-puranic-context` for retrieval-augmented generation (RAG) when generating context boxes.

For the full lifecycle from initialization to deployment, see `docs/end-to-end-workflow.md`.

**Pipeline:**
1. Extract raw text from the source file (PDF/TXT/MD)
2. Chunk text into ~4000-character segments
3. Use GPT-4o to extract structured episodes (id, type, keywords, summaries in English and Hindi)
4. Deduplicate episodes by ID
5. Embed each episode using the chosen embedding provider
6. Write episode index to `data/puranic-index/<key>.yml`
7. Write embeddings to `data/embeddings/puranic/<key>.json`
8. Register the source in `data/puranic-references.yml`

## Options

### Required

- `--file PATH` - Path to source file (`.pdf`, `.txt`, or `.md`)

### Optional

- `--force` - Re-index from scratch even if this source has already been indexed (re-runs all GPT-4o and embedding API calls)
- `--update-meta` - Patch `_meta` onto an existing index without re-indexing (fast — no API calls)
- `--chunk-size CHARS` - Characters per text chunk (default: `4000`). Increase for dense prose like Puranic texts; decrease for short-form content.
- `--provider {bedrock-cohere,openai}` - Embedding provider (default: `openai`). Use `bedrock-cohere` for better multilingual (Sanskrit/Hindi) accuracy.
- `--config PATH` - Embeddings config file (default: `_data/embeddings.yml`)
- `--project-dir PATH` - Project directory (default: current directory)

## Examples

```bash
# Index a PDF source
verse-index-sources --file data/sources/valmiki-ramayana.pdf

# Force re-index (re-runs all GPT-4o + embedding calls)
verse-index-sources --file data/sources/devi-bhagavata.txt --force

# Use a larger chunk size for dense Puranic prose (default: 4000)
verse-index-sources --file data/sources/shiv-puran.txt --chunk-size 6000

# Use Bedrock Cohere for better multilingual (Sanskrit/Hindi) accuracy
verse-index-sources --file data/sources/shiv-puran.txt --provider bedrock-cohere

# Patch _meta onto an existing index without re-indexing (fast)
verse-index-sources --file data/sources/shiv-puran-part1.txt --update-meta
```

## Output Files

### Episode Index

`data/puranic-index/<key>.yml` — `_meta` block followed by the episode list:

```yaml
_meta:
  source_file: valmiki-ramayana.pdf
  source_name: Valmiki Ramayana
  legend: "📜 Valmiki Ramayana"
  generated_at: 2026-02-21T10:30:00
  sdk_version: 0.30.6
  embedding_provider: openai
  embedding_model: text-embedding-3-small
  chunk_size: 4000
  episode_count: 842
episodes:
  - id: rama-exile-episode
    type: story
    keywords:
      - Rama
      - exile
      - forest
    source:
      book: Valmiki Ramayana
      sarga: Ayodhya Kanda, Sarga 20
    summary_en: "Rama accepts exile to honor his father Dasharatha's promise..."
    summary_hi: "राम ने अपने पिता दशरथ के वचन का सम्मान करते हुए वनवास स्वीकार किया..."
```

### Embeddings

`data/embeddings/puranic/<key>.json`:

```json
{
  "key": "valmiki-ramayana",
  "model": "text-embedding-3-small",
  "generated_at": "2026-02-21T10:30:00",
  "episodes": [
    {"id": "rama-exile-episode", "embedding": [0.12, -0.34, ...]}
  ]
}
```

### Migration Note

Puranic embeddings are now stored under `data/embeddings/puranic/`. If you have legacy files in `data/embeddings/<key>.json`, move them into the `puranic/` folder or re-run `verse-index-sources` to regenerate.

### References Registry

`data/puranic-references.yml` — tracks all indexed sources:

```yaml
valmiki-ramayana:
  enabled: true
  name: Valmiki Ramayana
  format: pdf
```

## Updating `_meta` on Existing Indexes

Indexes created before v0.30.5 are bare episode lists with no `_meta`. Use `--update-meta` to patch `_meta` in place without re-running the expensive GPT-4o and embedding pipeline:

```bash
verse-index-sources --file data/sources/shiv-puran-part1.txt --update-meta
```

This reads the existing episodes from the index file and the embedding model from the embeddings JSON, then writes `_meta` back alongside the unchanged episodes. The `--provider` flag sets the `embedding_provider` field in `_meta` — pass the provider that was originally used:

```bash
# If originally indexed with bedrock-cohere
verse-index-sources --file data/sources/shiv-puran-part1.txt --update-meta --provider bedrock-cohere
```

## Requirements

- `OPENAI_API_KEY` environment variable (for GPT-4o episode extraction)
- AWS credentials configured (for `bedrock-cohere` provider)
- `pdfplumber` installed for PDF sources (`pip install pdfplumber`)

## Config Defaults

If `_data/embeddings.yml` is present, `verse-index-sources` will use `active_provider` and `puranic_embeddings_dir` unless overridden by CLI flags.

## Workflow

```bash
# 1. Place source documents in data/sources/
mkdir -p data/sources
cp /path/to/valmiki-ramayana.pdf data/sources/

# 2. Index the source
verse-index-sources --file data/sources/valmiki-ramayana.pdf

# 3. Generate Puranic context for verses (RAG-grounded)
verse-puranic-context --collection hanuman-chalisa --all
```

## See Also

- [verse-puranic-context](verse-puranic-context.md) - Generate Puranic context boxes using indexed sources
