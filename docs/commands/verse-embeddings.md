# verse-embeddings

Generate vector embeddings for semantic search and RAG (Retrieval Augmented Generation).

## Synopsis

```bash
# Single collection mode (canonical output)
verse-embeddings --collection <key> --collections-file PATH [OPTIONS]

# Multi-collection mode (canonical output)
verse-embeddings --multi-collection --collections-file PATH [OPTIONS]

# Legacy combined output (opt-in)
verse-embeddings --multi-collection --collections-file PATH --legacy-output [--output PATH]
```

## Description

The `verse-embeddings` command generates vector embeddings for verses, enabling semantic search and AI-powered guidance features. It supports:
- For the full lifecycle from initialization to deployment, see `docs/end-to-end-workflow.md`.
- **Single collection mode**: Process one collection at a time
- **Multi-collection mode**: Process multiple collections at once
- **Canonical per-collection output**: `data/embeddings/collections/{collection}.json` + manifest
- **Legacy combined output** (opt-in): `data/embeddings.json`
- **OpenAI provider** (recommended): Higher quality, requires API key
- **HuggingFace provider** (free): Local models, no API key needed

Configuration precedence:
`CLI flags` > `env vars` > `providers.<active_provider>` > global config > `SDK defaults`

## Options

### Single Collection Mode

- `--collection KEY` - Collection key to process (e.g., `hanuman-chalisa`)
- `--collections-file PATH` - Path to collections.yml file (used to locate subdirectory)
- `--verses-dir PATH` - Base verses directory (default: `_verses/`)

### Multi-Collection Mode

- `--multi-collection` - Enable multi-collection processing
- `--collections-file PATH` - Path to collections.yml file (default: `_data/collections.yml`)
- `--verses-dir PATH` - Base verses directory (default: `_verses/`)

### Common Options

- `--provider PROVIDER` - Embedding provider: `openai`, `bedrock-cohere`, or `huggingface` (default: `openai`)
- `--model MODEL` - Model to use (provider-specific)
- `--output-dir PATH` - Output directory for canonical per-collection files (default: `data/embeddings/collections`)
- `--index-path PATH` - Manifest path (default: `<output-dir>/index.json`)
- `--config PATH` - Embeddings config file (default: `_data/embeddings.yml`)
- `--legacy-output` - Write legacy combined output (opt-in)
- `--output PATH` - Legacy combined output file path (used with `--legacy-output`)
- `--max-input-chars N` - Max input length (chars) per embedding request (defaults per provider)
- `--truncate-policy {drop,truncate,chunk}` - How to handle over-limit inputs (default: `chunk`)

## Examples

### Multi-Collection Mode (Recommended)

Process all enabled collections at once:

```bash
# Using OpenAI (recommended for quality)
verse-embeddings --multi-collection --collections-file _data/collections.yml

# Using HuggingFace (free, local)
verse-embeddings --multi-collection --collections-file _data/collections.yml --provider huggingface

### Bedrock Cohere Limits

Bedrock Cohere has strict input limits (default `2048` chars). If a verse exceeds this, the SDK will apply the selected policy:
- `chunk` (default): split into chunks and average embeddings
- `truncate`: truncate the last section to fit
- `drop`: drop low-priority sections until under limit
```

This processes all collections with `enabled: true` in `collections.yml` and creates per-collection embeddings under `data/embeddings/collections/` plus a manifest `data/embeddings/collections/index.json`.

### Single Collection Mode

Process one collection at a time:

```bash
# Using OpenAI (recommended)
verse-embeddings --collection hanuman-chalisa --collections-file _data/collections.yml

# Using HuggingFace (free)
verse-embeddings --collection hanuman-chalisa --collections-file _data/collections.yml --provider huggingface

# Multilingual Hugging Face model
verse-embeddings --collection hanuman-chalisa --collections-file _data/collections.yml \
  --provider huggingface --model sentence-transformers/paraphrase-multilingual-mpnet-base-v2

### Legacy Combined Output (Opt-in)

```bash
verse-embeddings --multi-collection --collections-file _data/collections.yml --legacy-output
```
```

### Provider Comparison

**OpenAI** (`text-embedding-3-small`):
- 1536 dimensions
- High quality semantic understanding
- Cost: ~$0.10 for 700 verses (one-time)

**HuggingFace** (`all-MiniLM-L6-v2`):
- 384 dimensions
- Good quality, runs locally
- No API key or cost
- First run downloads model (~80MB)

## Generated Output

### Per-Collection File (Canonical)

`data/embeddings/collections/{collection}.json`:

```json
{
  "collection": "hanuman-chalisa",
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "provider": "openai",
  "generated_at": "2024-01-15T10:30:00Z",
  "verses": {
    "en": [
      {
        "verse_number": 1,
        "title": "Shri Guru Charan Saroj Raj",
        "url": "/verses/verse-01/",
        "embedding": [0.123, -0.456, ...],
        "metadata": {
          "devanagari": "...",
          "transliteration": "...",
          "literal_translation": "..."
        }
      }
    ],
    "hi": [
      {
        "verse_number": 1,
        "title": "श्री गुरु चरण सरोज रज",
        "url": "/verses/verse-01/",
        "embedding": [0.123, -0.456, ...],
        "metadata": {
          "devanagari": "...",
          "transliteration": "...",
          "literal_translation": "..."
        }
      }
    ]
  }
}
```

### Manifest

`data/embeddings/collections/index.json`:

```json
{
  "generated_at": "2024-01-15T10:30:00Z",
  "collections": [
    {
      "collection": "hanuman-chalisa",
      "path": "hanuman-chalisa.json",
      "counts": { "en": 43, "hi": 43, "total": 43 },
      "checksum": "sha256...",
      "provider": "openai",
      "model": "text-embedding-3-small",
      "dimensions": 1536,
      "generated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

## Embedding Content

The command combines multiple fields from each verse:

- Sanskrit (devanagari)
- Transliteration
- Translations (English & Hindi)
- Word meanings
- Interpretive meaning
- Story/context
- Practical applications

This creates rich semantic embeddings that capture the full meaning of each verse.

## Workflow

### Multi-Collection Workflow

```bash
# 1. Ensure collections are configured
cat _data/collections.yml

# Optional: set defaults in _data/embeddings.yml
cat _data/embeddings.yml

# 2. Generate embeddings (one-time setup)
verse-embeddings --multi-collection --collections-file _data/collections.yml

# 3. Verify output
ls -lh data/embeddings/collections
cat data/embeddings/collections/index.json | jq '.collections'

# 4. Use in your application
# The embeddings file is loaded client-side for semantic search

# 5. Regenerate after adding new verses or collections
verse-embeddings --multi-collection --collections-file _data/collections.yml
```

### Single Collection Workflow

```bash
# 1. Generate embeddings for specific collection
verse-embeddings --collection hanuman-chalisa --collections-file _data/collections.yml

# 2. Verify output
cat data/embeddings/collections/hanuman-chalisa.json | jq '.collection'
```

## Integration Example

Client-side semantic search with multi-collection support (JavaScript):

```javascript
// Load manifest
const manifest = await fetch('/data/embeddings/collections/index.json').then(r => r.json());

// Load a specific collection
const entry = manifest.collections.find(c => c.collection === 'hanuman-chalisa');
const data = await fetch(`/data/embeddings/collections/${entry.path}`).then(r => r.json());
const { verses } = data;

// Search for relevant verses (works with both single and multi-collection)
function findRelevantVerses(query, topK = 3, filterCollection = null) {
  const queryEmbedding = await generateEmbedding(query);

  let filtered = verses.en;
  if (filterCollection && entry.collection !== filterCollection) {
    filtered = [];
  }

  const scores = filtered.map(verse => ({
    ...verse,
    score: cosineSimilarity(queryEmbedding, verse.embedding)
  }));

  return scores
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
}

// Search within specific collection
const hanumanResults = await findRelevantVerses("devotion", 5, "hanuman-chalisa");

## Migration Note

Canonical outputs are now per-collection (`data/embeddings/collections/{collection}.json`) with a manifest (`data/embeddings/collections/index.json`). Legacy combined output (`data/embeddings.json`) is only written when you pass `--legacy-output`.
```

## Cost & Performance

### OpenAI

- **Model**: text-embedding-3-small
- **Cost**: $0.00002 per 1,000 tokens
- **For Bhagavad Gita** (700 verses, ~500 tokens each):
  - Total tokens: ~350,000
  - Cost: ~$0.10 (one-time)
- **Generation time**: ~2-3 minutes

### HuggingFace

- **Model**: all-MiniLM-L6-v2
- **Cost**: Free
- **Download size**: ~80MB (first run only)
- **Generation time**: ~10-15 minutes (depends on CPU)
- **Memory**: ~500MB RAM

## Provider Comparison

| Feature | OpenAI | HuggingFace |
|---------|--------|-------------|
| Quality | Excellent | Good |
| Dimensions | 1536 | 384 |
| Cost | ~$0.10 | Free |
| Speed | Fast | Moderate |
| Setup | API key | Model download |
| Best for | Production | Development/testing |

## Requirements

### OpenAI Provider

- `OPENAI_API_KEY` environment variable
- Internet connection

### HuggingFace Provider

- Python packages: `torch`, `sentence-transformers`
- ~80MB disk space for model
- No API key needed

## Use Cases

1. **Semantic Search**: Find verses by meaning, not just keywords
2. **RAG Systems**: Provide context for AI spiritual guidance
3. **Similarity**: Find verses with similar themes
4. **Recommendations**: Suggest related verses to readers

## Notes

- Embeddings are generated once and reused (no need to regenerate on every query)
- Regenerate embeddings when adding new verses or collections
- The output JSON file can be loaded client-side (semantic search runs in browser)
- Multi-collection mode processes all enabled collections in `collections.yml`
- OpenAI embeddings are recommended for production (better quality)
- HuggingFace is great for development and testing (free, no API needed)
- Multi-collection output includes `collection` field for filtering

## See Also

- [Multi-Collection Guide](../multi-collection.md) - Detailed guide on working with multiple collections
- [OpenAI Embeddings Documentation](https://platform.openai.com/docs/guides/embeddings)
- [sentence-transformers Documentation](https://www.sbert.net/)
- [Troubleshooting](../troubleshooting.md) - Common issues

## Troubleshooting

### "Error: OPENAI_API_KEY not set"

For OpenAI provider:

```bash
export OPENAI_API_KEY=sk-...
```

Or use HuggingFace instead:

```bash
verse-embeddings --multi-collection --collections-file _data/collections.yml --provider huggingface
```

### "Error: No verse files found"

Check:
- Verse directory path is correct
- Directory contains `.md` files
- Files have YAML frontmatter

### "Out of memory" (HuggingFace)

HuggingFace model needs ~500MB RAM. If hitting limits:
- Close other applications
- Use OpenAI provider instead (no local processing)

## See Also

- [OpenAI Embeddings Documentation](https://platform.openai.com/docs/guides/embeddings)
- [sentence-transformers Documentation](https://www.sbert.net/)
- [Troubleshooting](../troubleshooting.md) - Common issues
