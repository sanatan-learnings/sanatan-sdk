# Sanatan Verse SDK - Python SDK for Spiritual Verse Collections

Complete toolkit for generating rich multimedia content for spiritual text collections (Hanuman Chalisa, Sundar Kaand, etc.)

## Features

- **🔄 Complete Workflow**: Generate media and embeddings from canonical sources - all in one command
- **📖 Canonical Sources**: Local YAML files ensure text accuracy and quality
- **🎨 AI Images**: Generate themed images with DALL-E 3
- **🎵 Audio Pronunciation**: Full and slow-speed audio with ElevenLabs
- **🔍 Semantic Search**: Vector embeddings for intelligent verse discovery
- **📚 Multi-Collection**: Organized support for multiple verse collections
- **🎨 Theme System**: Customizable visual styles (modern, traditional, kids-friendly, etc.)

## Quick Start

**Start here:** [End-to-End Workflow](docs/end-to-end-workflow.md)

### New Project Setup (Recommended)

```bash
# 1. Install
pip install sanatan-verse-sdk

# 2. Create project with collection templates
verse-init --project-name my-verse-project --collection hanuman-chalisa
cd my-verse-project

# 3. Configure API keys
cp .env.example .env
# Edit .env and add your API keys from:
# - OpenAI: https://platform.openai.com/api-keys
# - ElevenLabs: https://elevenlabs.io/app/settings/api-keys

# 4. Add canonical Devanagari text
# Edit data/verses/hanuman-chalisa.yaml with actual verse text

# 5. Validate setup
verse-validate

# 6. Generate multimedia content
verse-generate --collection hanuman-chalisa --verse 1
```

**What you get**: Verse file, AI-generated image, audio (full + slow speed), and search embeddings!

### Existing Project

```bash
# Validate and fix structure
verse-validate --fix

# Generate content
verse-generate --collection hanuman-chalisa --verse 15

# Check status
verse-status --collection hanuman-chalisa
```

### Advanced Usage

```bash
# Multiple collections at once
verse-init --collection hanuman-chalisa --collection sundar-kaand

# Custom number of sample verses
verse-init --collection my-collection --num-verses 10

# Generate specific components only
verse-generate --collection sundar-kaand --verse 3 --image
verse-generate --collection sundar-kaand --verse 3 --audio

# Skip embeddings update (faster)
verse-generate --collection hanuman-chalisa --verse 15 --no-update-embeddings
```

### What Gets Generated

Each verse generation creates:
- 🎨 **Image**: `images/{collection}/{theme}/verse-01.png` (DALL-E 3)
- 🎵 **Audio (full)**: `audio/{collection}/verse-01-full.mp3` (ElevenLabs)
- 🎵 **Audio (slow)**: `audio/{collection}/verse-01-slow.mp3` (0.75x speed)
- 🔍 **Embeddings**: `data/embeddings/collections/{collection}.json` + `data/embeddings/collections/index.json` (for semantic search)

**Text Source**: Canonical Devanagari text from `data/verses/{collection}.yaml` ([Local Verses Guide](docs/local-verses.md))

**Migration Note**: Legacy combined embeddings (`data/embeddings.json`) are no longer written by default. Use `verse-embeddings --legacy-output` if you still need the combined file.

## Puranic Context Generation

Enrich verse pages with grounded story references from indexed sacred texts. Two-stage workflow:

### Stage 1 — Index a Source Text

```bash
verse-index-sources --file data/sources/ananda-ramayana.txt
```

This command:
1. Splits the source text into ~4000-char chunks
2. Parses each chunk into discrete named episodes (keywords, type, summary in English + Hindi)
3. Generates embeddings for each episode
4. Writes outputs:
   - `data/puranic-index/{key}.yml` — human-readable episode index with `_meta` section
   - `data/embeddings/puranic/{key}.json` — embedding vectors for RAG retrieval
   - `data/puranic-references.yml` — registry of indexed sources

Only needs to run once per source, or when the source file changes.

```bash
# Use Bedrock Cohere for better Sanskrit/Hindi accuracy
verse-index-sources --file data/sources/shiv-puran.txt --provider bedrock-cohere

# If Bedrock input exceeds limits, use truncation policy
verse-embeddings --provider bedrock-cohere --truncate-policy chunk

# Larger chunk size for dense Puranic prose
verse-index-sources --file data/sources/valmiki-ramayana.pdf --chunk-size 6000
```

### Stage 2 — Generate Puranic Context per Verse

```bash
verse-puranic-context --collection hanuman-chalisa --all
```

For each verse this command:
1. Embeds the verse text using the same provider as the indexed source
2. Runs cosine similarity search across all indexed sources to find the most relevant episodes
3. Filters to episodes involving the collection's subject (configured in `_data/collections.yml`)
4. Passes top episodes + verse text to GPT-4o with citation constraints
5. Post-validates each entry: drops entries where the subject is not an active participant
6. Writes `puranic_context:` block into the verse's `.md` frontmatter

```bash
# Skip verses that already have context (default)
verse-puranic-context --collection hanuman-chalisa --all

# Regenerate all existing entries
verse-puranic-context --collection hanuman-chalisa --all --regenerate

# Single verse
verse-puranic-context --collection hanuman-chalisa --verse chaupai-06
```

### Collection Subject Configuration

The subject filter is resolved via a two-level hierarchy — no CLI flag needed:

**Option A — Project-level default** (single-subject projects): set once in `_data/verse-config.yml`, applies to all collections:

```yaml
# _data/verse-config.yml
defaults:
  subject: Hanuman
  subject_type: deity
```

**Option B — Collection-level override**: set per collection in `_data/collections.yml` (takes priority over project default):

```yaml
# _data/collections.yml
hanuman-chalisa:
  subject: Hanuman      # overrides or supplements project default
  subject_type: deity

krishna-bhajans:
  subject: Krishna      # different subject for this collection
  subject_type: deity
```

Resolution order: collection-level → project default → error if neither is set and indexed sources exist.

### Multiple Sources

Multiple indexed sources are automatically combined in RAG retrieval:

```
_data/verse-config.yml         ← set defaults.subject here

data/sources/
  shiv-puran-part1.txt
  ananda-ramayana.txt        ← add new sources here

data/puranic-index/
  shiv-puran-part1.yml       ← auto-generated episode index
  ananda-ramayana.yml

data/embeddings/
  puranic/
    shiv-puran-part1.json      ← auto-generated embedding vectors
    ananda-ramayana.json
```

See [verse-index-sources](docs/commands/verse-index-sources.md) and [verse-puranic-context](docs/commands/verse-puranic-context.md) for full documentation.

**Migration Note**: Puranic embeddings now live under `data/embeddings/puranic/`. If you have legacy files in `data/embeddings/{source}.json`, move them or re-run `verse-index-sources` to regenerate.

## Installation

```bash
pip install sanatan-verse-sdk
```

## Commands

### Project Setup
- **[verse-init](docs/commands/verse-init.md)** - Initialize new project with recommended structure
- **[verse-validate](docs/commands/verse-validate.md)** - Validate project structure and configuration

### Content Generation
- **[verse-generate](docs/commands/verse-generate.md)** - Complete orchestrator for verse content (text fetching, multimedia generation, embeddings)
- **[verse-translate](docs/commands/verse-translate.md)** - Translate verses into multiple languages (Hindi, Spanish, French, etc.)
- **[verse-images](docs/commands/verse-images.md)** - Generate images using DALL-E 3
- **[verse-audio](docs/commands/verse-audio.md)** - Generate audio pronunciations using ElevenLabs
- **[verse-embeddings](docs/commands/verse-embeddings.md)** - Generate vector embeddings for semantic search ([multi-collection guide](docs/multi-collection.md))

### Puranic Context
- **[verse-index-sources](docs/commands/verse-index-sources.md)** - Index Puranic source texts (PDFs, TXTs) into episodes and embeddings for RAG retrieval
- **[verse-puranic-context](docs/commands/verse-puranic-context.md)** - Generate Puranic context boxes for verses (RAG-grounded or GPT-4o free recall)

### Project Management
- **[verse-add](docs/commands/verse-add.md)** - Add new verse entries to collections (supports multi-chapter formats)
- **[verse-status](docs/commands/verse-status.md)** - Check status, completion, and validate text against canonical source
- **[verse-sync](docs/commands/verse-sync.md)** - Sync verse text with canonical source (fix mismatches)
- **[verse-deploy](docs/commands/verse-deploy.md)** - Deploy Cloudflare Worker for API proxy

### Embeddings Config
- **[embeddings.yml](docs/embeddings-config.md)** - Shared defaults and precedence (CLI > config > env > defaults)

## Configuration

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
# Edit .env and add your API keys
```

See the [End-to-End Workflow](docs/end-to-end-workflow.md) for the full lifecycle, and the [Usage Guide](docs/usage.md) for advanced workflows and best practices.

## Documentation

- **[End-to-End Workflow](docs/end-to-end-workflow.md)** - Initialize, generate, index, and deploy (full lifecycle)
- **[Usage Guide](docs/usage.md)** - Advanced workflows, batch processing, and best practices
- **[Local Verses Guide](docs/local-verses.md)** - Using local YAML files for verse text
- **[Chapter-Based Formats](docs/chapter-based-formats.md)** - Multi-chapter collections (Bhagavad Gita, etc.)
- **[Command Reference](docs/README.md)** - Detailed documentation for all commands
- **[Development Guide](docs/development.md)** - Setup and contributing to verse-sdk
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Multi-Collection Guide](docs/multi-collection.md)** - Working with multiple collections
- **[Publishing Guide](docs/publishing.md)** - For maintainers

## Example Project

[Hanuman GPT](https://github.com/sanatan-learnings/hanuman-gpt) - Multi-collection project with Hanuman Chalisa, Sundar Kaand, and Sankat Mochan Hanumanashtak

## Requirements

- Python 3.8+
- OpenAI API key (for text/images/embeddings)
- ElevenLabs API key (for audio)

## License

MIT License - See [LICENSE](LICENSE) file for details

## Support

- [GitHub Issues](https://github.com/sanatan-learnings/sanatan-verse-sdk/issues)
- [Documentation](docs/README.md)
- [Troubleshooting Guide](docs/troubleshooting.md)
