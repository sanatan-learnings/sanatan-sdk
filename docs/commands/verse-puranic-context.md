# verse-puranic-context

Generate Puranic context boxes for verse files using RAG retrieval or GPT-4o free recall.

## Synopsis

```bash
verse-puranic-context --collection COLLECTION (--verse ID | --all) [OPTIONS]
```

## Description

`verse-puranic-context` uses AI to identify relevant Puranic references (stories, characters, concepts, etymologies) and injects a `puranic_context` block into each verse file's frontmatter.

For the full lifecycle from initialization to deployment, see `docs/end-to-end-workflow.md`.

**RAG mode (recommended):** When indexed sources are available (`data/puranic-references.yml` + `data/puranic-index/`), the command embeds the verse text, retrieves the most relevant Puranic episodes via cosine similarity, and provides them as grounding context to GPT-4o.

**Free-recall fallback:** If no sources are indexed, the command prompts you to continue with GPT-4o's built-in knowledge. Use `verse-index-sources` to add indexed sources and switch to RAG mode.

## Options

### Required

- `--collection KEY` - Collection key (e.g., `hanuman-chalisa`, `sundar-kaand`)
- `--verse ID` or `--all` - Process a specific verse ID, or all verses in the collection (mutually exclusive)

### Optional

- `--regenerate` - Overwrite existing `puranic_context` entries (default: skip verses that already have context)
- `--project-dir PATH` - Project directory (default: current directory)

## Examples

```bash
# Generate for a specific verse
verse-puranic-context --collection hanuman-chalisa --verse chaupai-15

# Generate for all verses missing context
verse-puranic-context --collection bajrang-baan --all

# Force regenerate even if context exists
verse-puranic-context --collection hanuman-chalisa --verse chaupai-18 --regenerate

# Regenerate all verses in a collection
verse-puranic-context --collection sundar-kaand --all --regenerate
```

## Collection Configuration

Subject filtering is configured in `_data/collections.yml`, not via CLI flags. Add `subject` and `subject_type` fields to your collection entry:

```yaml
hanuman-chalisa:
  enabled: true
  name:
    en: Hanuman Chalisa
    hi: हनुमान चालीसा
  subject: Hanuman        # primary deity/subject of this collection
  subject_type: deity     # deity | avatar | concept | figure
  permalink_base: /hanuman-chalisa
  total_verses: 43

sundar-kaand:
  enabled: true
  name:
    en: Sundar Kaand
    hi: सुंदर काण्ड
  subject: Hanuman
  subject_type: deity
  permalink_base: /sundar-kaand
  total_verses: 68
```

If indexed sources are available and `subject` is not set, the command will exit with an error and instructions to add it.

**`subject_type`** labels the subject in the GPT-4o prompt. Use appropriate values for non-deity subjects:

```yaml
# For a philosophical text
upanishads:
  subject: Brahman
  subject_type: concept

# For a Rama-centric collection
ramayana:
  subject: Rama
  subject_type: avatar
```

## Subject Filtering

When indexing a broad source like Shiv Puran, RAG retrieval can surface episodes about Parvati, Shiva, or Nandi for verses that are specifically about Hanuman. The `subject` field in `_data/collections.yml` keeps context relevant.

**What it does in three layers:**

1. **Pre-filter (keyword):** After RAG retrieval, drops episodes where the subject name does not appear in the episode's keywords, id, or summary.

2. **Prompt constraint (LLM):** Instructs GPT-4o to only generate `puranic_context` entries where the subject is a direct participant.

3. **Post-generation validation:** A second GPT-4o-mini call verifies that each generated entry actually involves the subject as an active participant — entries where the subject is only thematically connected are dropped.

**Fallback:** If the keyword filter removes all retrieved episodes, it falls back to the full retrieved set so generation still runs with the prompt constraint applied.

## Output

Each processed verse file gets a `puranic_context` block added to its YAML frontmatter:

```yaml
puranic_context:
  - id: hanuman-leaping-ocean
    type: story
    priority: high
    title:
      en: Hanuman's Leap Across the Ocean
      hi: हनुमान का समुद्र लांघना
    icon: 🌊
    story_summary:
      en: "Hanuman leaps across the ocean to Lanka in search of Sita..."
      hi: "हनुमान सीता की खोज में समुद्र लांघकर लंका पहुंचते हैं..."
    theological_significance:
      en: "Symbolises the power of devotion to overcome all obstacles..."
      hi: "भक्ति की शक्ति से सभी बाधाओों पर विजय का प्रतीक..."
    practical_application:
      en: "Chanting this verse invokes Hanuman's strength in times of difficulty..."
      hi: "इस चौपाई का पाठ कठिन समय में हनुमान की शक्ति का आह्वान करता है..."
    source_texts:
      - text: Shiv Puran
        section: Part 1
    related_verses: []
```

### Context Entry Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique kebab-case slug |
| `type` | enum | `story`, `concept`, `character`, `etymology`, `practice`, `cross_reference` |
| `priority` | enum | `high`, `medium`, `low` |
| `title.en` / `title.hi` | string | English and Hindi title |
| `icon` | string | Single emoji |
| `story_summary` | object | 2-4 sentence summary (en + hi) |
| `theological_significance` | object | Spiritual meaning (en + hi) |
| `practical_application` | object | Practical use (en + hi) |
| `source_texts` | list | Indexed sources only (constrained to avoid hallucination) |
| `related_verses` | list | Cross-references to other verses |

## RAG Workflow

```bash
# 1. Add subject to _data/collections.yml
#    subject: Hanuman
#    subject_type: deity

# 2. Index source texts
verse-index-sources --file data/sources/shiv-puran-part1.txt

# 3. Generate context (subject read automatically from collections.yml)
verse-puranic-context --collection hanuman-chalisa --all
```

Each verse is embedded using the same provider as the indexed source (detected from `_meta.embedding_provider`) and matched against indexed episodes to select the top-8 most relevant passages as grounding context.

## Migration Note

Puranic embeddings are now read from `data/embeddings/puranic/<key>.json`. If you have legacy files in `data/embeddings/<key>.json`, move them into the `puranic/` folder or re-run `verse-index-sources`.

## Requirements

- `OPENAI_API_KEY` environment variable
- Verse files in `_verses/<collection>/<verse-id>.md` with YAML frontmatter
- `subject` and `subject_type` fields in `_data/collections.yml` (required when indexed sources are present)
- AWS credentials only if using `bedrock-cohere` indexed sources

## Config Defaults

If `_data/embeddings.yml` is present, `verse-puranic-context` will use `puranic_embeddings_dir` for loading episode embeddings (unless overridden by CLI flags).

## See Also

- [verse-index-sources](verse-index-sources.md) - Index Puranic source texts for RAG retrieval
- [verse-generate](verse-generate.md) - Generate full verse content (translation, images, audio, embeddings)
