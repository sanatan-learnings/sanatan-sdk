# verse-generate

Complete orchestration for verse content generation including scene description generation, multimedia (images and audio), and embeddings. Supports batch processing with range syntax.

## Synopsis

```bash
verse-generate --collection COLLECTION --verse N [OPTIONS]
verse-generate --collection COLLECTION --verse M-N [OPTIONS]  # Batch processing
```

## Description

The `verse-generate` command is a complete orchestrator for verse content generation. **By default**, it executes the multimedia workflow:
- Reads canonical Devanagari text from local sources
- Automatically generates scene descriptions using GPT-4 (saved to `data/scenes/<collection>.md`)
- Generates images using DALL-E 3 based on scene descriptions
- Generates audio pronunciations using ElevenLabs (full-speed and slow-speed)

Embeddings are **not** updated by default. Use `--embeddings` to opt-in, or run `verse-embeddings` separately after batch generation.

Additionally, you can regenerate AI content (transliteration, meaning, translation, story) from the canonical source using `--regenerate-content`.

**Batch Processing**: Use range syntax `--verse M-N` (e.g., `1-10`) to generate multiple verses in one command.

## Options

### Required

- `--collection NAME` - Collection key (e.g., `hanuman-chalisa`, `sundar-kaand`)
- `--verse N or M-N` - Verse number (e.g., `5`) or range (e.g., `1-10`, `5-20`) for batch processing
  - **OR** use `--next` to auto-detect the next missing verse

### Optional

- `--next` - Auto-detect and generate the next missing verse in sequence (requires canonical YAML file)

- `--all` - Generate both image and audio (this is the default behavior if no flags specified)
- `--image` - Generate image only
- `--audio` - Generate audio only
- `--regenerate-content` - Regenerate AI content (transliteration, meaning, translation, story) from canonical Devanagari text in `data/verses/{collection}.yaml`
- `--embeddings` - Update vector embeddings after generation (opt-in; use `verse-embeddings` for batch updates)
- `--theme NAME` - Image theme name (default: modern-minimalist)
- `--verse-id ID` - Override verse identifier (e.g., chaupai_05, doha_01). Auto-detected if not specified
- `--list-collections` - List all available collections

## Examples

### List Available Collections

```bash
verse-generate --list-collections
```

### Auto-Detect Next Missing Verse

Generate the next verse that hasn't been implemented yet:

```bash
verse-generate --collection bhagavad-gita --next --all
```

**How it works:**
1. Reads the canonical verse sequence from `data/verses/bhagavad-gita.yaml`
2. Checks which verses already have files in `_verses/bhagavad-gita/`
3. Finds the **first missing verse** (lowest number not yet implemented)
4. Generates all content for that verse

**Example:**
- Canonical file has verses: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
- Existing files: verse-01.md, verse-02.md, verse-03.md, verse-06.md, verse-07.md
- Missing: verse-04, verse-05, verse-08, verse-09, verse-10
- `--next` will generate: **verse-04** (first missing)

**Requirements:**
- Canonical YAML file must exist at `data/verses/<collection>.yaml`
- File defines the proper verse sequence
- If file is missing, use `verse-add` or `verse-validate --fix` to create it

### Complete Workflow (Default)

The simplest form runs the complete workflow:

```bash
verse-generate --collection hanuman-chalisa --verse 15
```

This automatically:
1. Reads canonical Devanagari text from local source
2. Generates scene description using GPT-4 (saved to `data/scenes/hanuman-chalisa.md`)
3. Generates DALL-E 3 image using scene description (modern-minimalist theme)
4. Generates full-speed audio pronunciation
5. Generates slow-speed audio pronunciation (0.75x)

Embeddings are **not** updated by default. Run `verse-embeddings` once after batch generation.

### Batch Processing

Generate multiple verses in one command using range syntax:

```bash
# Generate verses 1 through 10
verse-generate --collection hanuman-chalisa --verse 1-10

# Generate verses 5 through 20 with custom theme
verse-generate --collection sundar-kaand --verse 5-20 --theme kids-friendly

# Generate range, then update embeddings once at the end
verse-generate --collection hanuman-chalisa --verse 1-10
verse-embeddings --multi-collection --collections-file _data/collections.yml --verses-dir _verses

# Generate range with content regeneration
verse-generate --collection sundar-kaand --verse 1-5 --regenerate-content
```

**Batch Features:**
- Progress tracking shows "Processing verse X/Y: Verse N"
- Embeddings updated once at the end (optimized for batch)
- Continues on errors (doesn't stop entire batch)
- Summary shows success/failure breakdown

### Update Embeddings

Embeddings are off by default. To update them after generation:

```bash
# Include embeddings for a single verse
verse-generate --collection hanuman-chalisa --verse 15 --embeddings

# Or run verse-embeddings once after batch generation (recommended)
verse-embeddings --multi-collection --collections-file _data/collections.yml \
  --verses-dir _verses
```

### Custom Theme

Use a different theme:

```bash
verse-generate --collection hanuman-chalisa --verse 15 --theme kids-friendly
```

### Generate Specific Components

```bash
# Only image
verse-generate --collection sundar-kaand --verse 3 --image --theme modern-minimalist

# Only audio
verse-generate --collection sankat-mochan-hanumanashtak --verse 5 --audio

# Image and audio with specific theme
verse-generate --collection hanuman-chalisa --verse 20 --all --theme kids-friendly
```

### Regenerate AI Content

When you update the canonical Devanagari text in `data/verses/{collection}.yaml` and want to regenerate all AI-generated content:

```bash
# Regenerate only AI content (transliteration, meaning, translation, story)
verse-generate --collection sundar-kaand --verse 3 --regenerate-content

# Regenerate AI content AND multimedia
verse-generate --collection sundar-kaand --verse 3 --regenerate-content --all

# Regenerate content only
verse-generate --collection sundar-kaand --verse 3 --regenerate-content
```

This reads the canonical Devanagari text from `data/verses/{collection}.yaml` and uses GPT-4 to generate:
- Transliteration (IAST format)
- Word-by-word meaning
- English translation
- Story & context (2-3 paragraphs)
- Practical applications (2-3 ways to apply teachings)

### Different Collections

```bash
# Hanuman Chalisa
verse-generate --collection hanuman-chalisa --verse 12

# Sundar Kaand (verse ID auto-detected)
verse-generate --collection sundar-kaand --verse 3

# Sankat Mochan Hanumanashtak
verse-generate --collection sankat-mochan-hanumanashtak --verse 7
```

## Generated Files

When using default (or `--all`), the command creates:

1. **Scene description**: `data/scenes/<collection-key>.md`
   - Automatically generated using GPT-4 from canonical Devanagari text
   - Always regenerated to ensure consistency with source text
   - Format: `### Verse N: title` followed by `**Scene Description:**`

2. **Image**: `images/<collection-key>/<theme-name>/verse-NN.png`
   - Generated by DALL-E 3 using scene description
   - Portrait format (1024x1792)
   - Styled according to theme configuration

3. **Audio files**: `audio/<collection-key>/verse_NN_*.mp3`
   - `verse_NN_full.mp3` - Full speed
   - `verse_NN_slow.mp3` - Slow speed (0.75x)

## Workflow

```bash
# 1. List available collections
verse-generate --list-collections

# 2. Generate everything for a verse (uses default modern-minimalist theme)
verse-generate --collection hanuman-chalisa --verse 15

# 3. Review generated files
open images/hanuman-chalisa/modern-minimalist/verse-15.png
afplay audio/hanuman-chalisa/verse_15_full.mp3

# 4. Commit
git add images/ audio/
git commit -m "Add media for Hanuman Chalisa verse 15"
```

### Regenerate Specific Components

```bash
# Regenerate just the image (with default theme)
verse-generate --collection hanuman-chalisa --verse 15 --image

# Regenerate just the image with custom theme
verse-generate --collection hanuman-chalisa --verse 15 --image --theme kids-friendly

# Regenerate just the audio
verse-generate --collection hanuman-chalisa --verse 15 --audio
```

## Requirements

- **For --image**: `OPENAI_API_KEY` + theme config in `data/themes/<collection-key>/<theme-name>.yml`
  - Scene descriptions are automatically generated in `data/scenes/<collection-key>.md` if they don't exist
- **For --audio**: `ELEVENLABS_API_KEY` + verse file with `devanagari:` field
- **For --regenerate-content**: `OPENAI_API_KEY` + canonical text in `data/verses/<collection>.yaml`
- **For --update-embeddings**: `OPENAI_API_KEY` for generating vector embeddings
- Collection must be enabled in `_data/collections.yml`

## Notes

- **Default behavior**: Generates image + audio with `modern-minimalist` theme. Embeddings are **not** updated by default.
- **Embeddings**: Use `--embeddings` to update after a single verse, or run `verse-embeddings` once after batch generation
- **Batch processing**: Use range syntax `--verse M-N` to generate multiple verses (e.g., `1-10`, `5-20`)
- **Scene descriptions**: Automatically generated using GPT-4 and saved to `data/scenes/<collection-key>.md`
  - Scene descriptions are always regenerated from the canonical Devanagari text for consistency
- Use `--image` or `--audio` to generate only specific components
- Use `--theme` to change from the default `modern-minimalist` theme
- Verse ID is automatically detected from existing verse files (e.g., if `chaupai_05.md` exists, uses `chaupai_05`)
- Use `--verse-id` to override auto-detection when multiple files match (e.g., both `chaupai_05.md` and `doha_05.md` exist)
- For new verses without files, defaults to `verse_{N:02d}` format
- Theme configuration must exist in `data/themes/<collection-key>/<theme-name>.yml` for image generation
- Audio generation reads from the `devanagari:` field in verse files
- Only enabled collections (in `collections.yml`) can be processed

## See Also

- [verse-translate](verse-translate.md) - Translate verses into multiple languages
- [verse-status](verse-status.md) - Check status and validate text
- [verse-sync](verse-sync.md) - Sync verse text with canonical source
- [verse-images](verse-images.md) - Image generation details
- [verse-audio](verse-audio.md) - Audio generation details
- [verse-embeddings](verse-embeddings.md) - Vector embeddings for semantic search
- [Troubleshooting](../troubleshooting.md) - Common issues
