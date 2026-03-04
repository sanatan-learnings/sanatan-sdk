# verse-parse-source

Parse canonical source text into `data/verses/<collection>.yaml`.

## Synopsis

```bash
verse-parse-source --collection <key> [OPTIONS]
verse-parse-source --collection <key> --source <file> [OPTIONS]
verse-parse-source --collection <key> --source-dir <dir> --source-glob "<glob>" [OPTIONS]
```

## Description

`verse-parse-source` converts plain text source files into the canonical YAML format used by the SDK. It supports multi-file ingestion, deterministic output ordering, and read-only inspection via `--dry-run` and `--diff`.

When `--source` and `--source-dir` are omitted, the command auto-discovers input from `--collection`:
1. `data/sources/<collection>.txt`
2. `data/sources/<collection>/` (using default glob `**/*.txt`)

If both exist, file input is preferred.

For the full lifecycle from initialization to deployment, see `docs/end-to-end-workflow.md`.

## Options

- `--collection KEY` - Collection key (e.g., `hanuman-chalisa`)
- `--source PATH` - Source file path (repeatable)
- `--source-dir DIR` - Directory containing source files
- `--source-glob GLOB` - Glob for source files under `--source-dir` (default: `**/*.txt`)
- `--format {devanagari-plain,chaptered-plain}` - Parsing mode (default: `devanagari-plain`; auto-switches to `chaptered-plain` when chapter markers are detected and `--format` is omitted)
- `--profile {default,srimad-bhagavat}` - Parser profile for corpus-specific heuristics
- `--output PATH` - Output YAML path (default: `data/verses/<collection>.yaml`)
- `--dry-run` - Print summary without writing output
- `--diff` - Show unified diff if output changes
- `--filter-frontmatter {true,false}` - Drop front-matter lines before the first verse (default: `true`)
- `--filter-ocr-noise {true,false}` - Drop noisy OCR lines (default: `true`)
- `--frontmatter-max-lines N` - Max initial lines to scan for front-matter (default: `300`)
- `--noise-threshold N` - Noise threshold from `0.0` to `1.0` (default: `0.65`)
- `--report PATH` - Write parse report JSON
- `--expected-count-min N` - Warn if verse count is below this value
- `--expected-count-max N` - Warn if verse count exceeds this value
- `--start-marker TEXT` - Start parsing after this marker string
- `--start-marker-regex REGEX` - Start parsing after regex match
- `--disable-start-anchor` - Disable profile start-anchor behavior
- `--disable-heading-filter` - Disable profile heading-line filter
- `--chapter-scope {global,file}` - Chapter numbering scope (default: `global`)
- `--canto-regex REGEX` - Extract canto number from filename (used for key prefixing)

## Formats

### `devanagari-plain`

Treats blank-line separated paragraphs as verses. If there are no blank lines, each non-empty line is a verse. Output keys are `verse-01`, `verse-02`, ...

If `--format` is omitted and chapter markers are detected (e.g., `०.१. ...अध्यायः`), the parser automatically switches to `chaptered-plain`.

### `chaptered-plain`

Detects chapter headings like `Chapter 2` or `अध्याय 2`. Verses are grouped per chapter and output keys use `chapter-02-shloka-01`, `chapter-02-shloka-02`, ...

## Examples

```bash
# Auto-discovery (recommended common case)
verse-parse-source --collection hanuman-chalisa

# Single file
verse-parse-source \
  --collection hanuman-chalisa \
  --source data/sources/hanuman-chalisa.txt

# Multi-file (ordered by glob)
verse-parse-source \
  --collection srimad-bhagavat \
  --source-dir data/sources/srimad-bhagavat \
  --source-glob "volume-*/**/*.txt"

# Chaptered text
verse-parse-source \
  --collection bhagavad-gita \
  --source data/sources/bhagavad-gita.txt \
  --format chaptered-plain

# Safe inspection
verse-parse-source \
  --collection hanuman-chalisa \
  --source data/sources/hanuman-chalisa.txt \
  --dry-run --diff --report parse-report.json

# Srimad Bhagavat profile with guardrails
verse-parse-source \
  --collection srimad-bhagavat \
  --source-dir data/sources/srimad-bhagavat \
  --source-glob "volume-*/**/*.txt" \
  --profile srimad-bhagavat \
  --expected-count-min 16000 \
  --expected-count-max 20000

# Per-file chapter scope with canto prefix
verse-parse-source \
  --collection srimad-bhagavat \
  --source-dir data/sources/srimad-bhagavat \
  --source-glob "canto-*.txt" \
  --format chaptered-plain \
  --chapter-scope file \
  --canto-regex "canto-(\\d+)"

# Custom anchor override
verse-parse-source \
  --collection srimad-bhagavat \
  --source-dir data/sources/srimad-bhagavat \
  --source-glob "volume-*/**/*.txt" \
  --profile srimad-bhagavat \
  --start-marker "श्रीमदभागवत-माहात्म्य"

# Disable filtering (if needed)
verse-parse-source \
  --collection hanuman-chalisa \
  --source data/sources/hanuman-chalisa.txt \
  --filter-frontmatter false --filter-ocr-noise false
```
