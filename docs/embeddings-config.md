# Embeddings Config

Use `_data/embeddings.yml` to set project-wide defaults for embedding providers, models, and output paths. CLI flags always win, then environment variables, then provider-specific config, then global config, then SDK defaults.

## Example

```yaml
active_provider: openai
active_model: text-embedding-3-small
output_dir: data/embeddings/collections
index_path: data/embeddings/collections/index.json
puranic_embeddings_dir: data/embeddings/puranic
max_input_chars: 2048
truncate_policy: chunk
#
# Hugging Face example:
# active_provider: huggingface
# active_model: sentence-transformers/paraphrase-multilingual-mpnet-base-v2

## Provider Map Example

```yaml
active_provider: bedrock-cohere
providers:
  openai:
    model: text-embedding-3-small
    index_path: data/embeddings/providers/openai/collections/index.json
  bedrock-cohere:
    model: cohere.embed-multilingual-v3
    index_path: data/embeddings/providers/bedrock-cohere-embed-multilingual-v3/collections/index.json
  huggingface:
    model: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
    index_path: data/embeddings/providers/huggingface-paraphrase-multilingual-mpnet-base-v2/collections/index.json
```
```

## Precedence

1. CLI flags (highest)
2. Environment variables
3. Provider config (`providers.<active_provider>`)
4. Global config (flat keys like `active_model`, `output_dir`)
5. SDK defaults (lowest)

CLI overrides are logged, for example:

`Using provider=bedrock-cohere from CLI flag (overrides config: openai).`

## Environment Variables

- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `EMBEDDINGS_OUTPUT_DIR`
- `EMBEDDINGS_INDEX_PATH`
- `EMBEDDINGS_MAX_INPUT_CHARS`
- `EMBEDDINGS_TRUNCATE_POLICY`
- `PURANIC_EMBEDDINGS_DIR`

## Supported Commands

- `verse-embeddings` (provider/model/output/index)
- `verse-index-sources` (provider + puranic embeddings dir)
- `verse-puranic-context` (puranic embeddings dir)
