# Multi-Collection Support

Process multiple verse collections in a single command with the `verse-embeddings` tool.

## Quick Start

```bash
# Create collections.yml
cat > collections.yml << EOF
hanuman-chalisa:
  key: "hanuman-chalisa"
  name_en: "Hanuman Chalisa"
  subdirectory: "hanuman-chalisa"
  enabled: true
EOF

# Generate embeddings for all enabled collections
verse-embeddings --multi-collection --collections-file ./collections.yml
```

## Features

- Process multiple collections in one command
- Per-collection embeddings output with manifest
- Uses permalinks from verse frontmatter
- Backward compatible with single-collection mode
- Enable/disable collections via YAML

## Usage

### Single Collection (Default)

```bash
verse-embeddings --provider openai --collection hanuman-chalisa --collections-file ./_data/collections.yml
```

### Multi-Collection

```bash
# Process all enabled collections
verse-embeddings --multi-collection --collections-file ./collections.yml

# With specific provider
verse-embeddings --multi-collection \
  --collections-file ./_data/collections.yml \
  --provider huggingface
```

## Configuration

### Collections File Format

```yaml
collection-key:
  key: "collection-key"           # Required: Unique identifier
  name_en: "Collection Name"      # Required: English name
  subdirectory: "collection-dir"  # Required: Directory under _verses/
  enabled: true                   # Required: Enable/disable flag
  name_hi: "हिंदी नाम"            # Optional: Hindi name
  permalink_base: "/base/"        # Optional: Base URL (for reference)
```

### Directory Structure

```
project/
├── collections.yml or _data/collections.yml
├── _verses/
│   ├── collection-1/
│   │   ├── verse_01.md
│   │   └── ...
│   └── collection-2/
│       └── ...
└── data/
    └── embeddings/
        └── collections/
            ├── index.json
            ├── collection-1.json
            └── collection-2.json
```

### Verse Frontmatter

Add a `permalink` field to each verse file:

```yaml
---
permalink: /collection/verse_01/
title_en: "Verse 1: Title"
verse_number: 1
---
```

## Output Format

Each verse includes collection metadata:

```json
{
  "verses": {
    "en": [
      {
        "title": "Verse 1: Title",
        "url": "/collection/verse_01/",
        "embedding": [...],
        "metadata": {
          "devanagari": "...",
          "transliteration": "...",
          "collection_key": "collection-key",
          "collection_name": "Collection Name"
        }
      }
    ]
  }
}
```

## Verification

```bash
# Count verses per collection
cat data/embeddings/collections/index.json | jq '.collections | map({collection, count: .counts.total})'

# View sample verses for a collection
cat data/embeddings/collections/collection-1.json | jq '.verses.en[] | {title, collection: .collection}' | head -10
```

## Migration from Single Collection

1. Create `collections.yml` with your collections
2. Organize verses into subdirectories under `_verses/`
3. Add `permalink` fields to verse frontmatter
4. Run with `--multi-collection --collections-file ./collections.yml`

Single-collection workflows use `--collection <key> --collections-file ./collections.yml`.
