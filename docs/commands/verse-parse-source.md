# verse-parse-source

Parse canonical source text into `data/verses/<collection>.yaml`.

## Synopsis

```bash
verse-parse-source --collection <key> --source <file> [OPTIONS]
verse-parse-source --collection <key> --source-dir <dir> --source-glob "<glob>" [OPTIONS]
```

## Description

`verse-parse-source` converts plain text source files into the canonical YAML format used by the SDK. It supports multi-file ingestion, deterministic output ordering, and read-only inspection via `--dry-run` and `--diff`.

For the full lifecycle from initialization to deployment, see `docs/end-to-end-workflow.md`.

## Options

- `--collection KEY` - Collection key (e.g., `hanuman-chalisa`)
- `--source PATH` - Source file path (repeatable)
- `--source-dir DIR` - Directory containing source files
- `--source-glob GLOB` - Glob for source files under `--source-dir` (default: `**/*.txt`)
- `--format {devanagari-plain,chaptered-plain}` - Parsing mode (default: `devanagari-plain`)
- `--output PATH` - Output YAML path (default: `data/verses/<collection>.yaml`)
- `--dry-run` - Print summary without writing output
- `--diff` - Show unified diff if output changes
- `--filter-frontmatter {true,false}` - Drop front-matter lines before the first verse (default: `true`)
- `--filter-ocr-noise {true,false}` - Drop noisy OCR lines (default: `true`)
- `--frontmatter-max-lines N` - Max initial lines to scan for front-matter (default: `300`)
- `--noise-threshold N` - Noise threshold from `0.0` to `1.0` (default: `0.65`)
- `--report PATH` - Write parse report JSON

## Formats

### `devanagari-plain`

Treats blank-line separated paragraphs as verses. If there are no blank lines, each non-empty line is a verse. Output keys are `verse-01`, `verse-02`, ...

### `chaptered-plain`

Detects chapter headings like `Chapter 2` or `अध्याय 2`. Verses are grouped per chapter and output keys use `chapter-02-shloka-01`, `chapter-02-shloka-02`, ...

## Examples

```bash
# Single file
verse-parse-source \
  --collection hanuman-chalisa \
  --source data/source-texts/hanuman-chalisa.txt

# Multi-file (ordered by glob)
verse-parse-source \
  --collection srimad-bhagavat \
  --source-dir data/source-texts/srimad-bhagavat \
  --source-glob "volume-*/**/*.txt"

# Chaptered text
verse-parse-source \
  --collection bhagavad-gita \
  --source data/source-texts/bhagavad-gita.txt \
  --format chaptered-plain

# Safe inspection
verse-parse-source \
  --collection hanuman-chalisa \
  --source data/source-texts/hanuman-chalisa.txt \
  --dry-run --diff --report parse-report.json

# Disable filtering (if needed)
verse-parse-source \
  --collection hanuman-chalisa \
  --source data/source-texts/hanuman-chalisa.txt \
  --filter-frontmatter false --filter-ocr-noise false
```
