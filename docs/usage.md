# Usage Guide

This guide focuses on advanced workflows, batch processing, and operational best practices. For the full lifecycle walkthrough, start with `docs/end-to-end-workflow.md`.

## Table of Contents

- [Batch Processing](#batch-processing)
- [Chapter-Based Collections](#chapter-based-collections)
- [Theme Customization](#theme-customization)
- [API Costs](#api-costs)
- [Best Practices](#best-practices)

## Batch Processing

Process large collections efficiently by generating assets in batches and updating embeddings once at the end.

```bash
# Generate assets without updating embeddings each time
for i in $(seq 1 40); do
  verse-generate --collection hanuman-chalisa --verse $i --no-update-embeddings
done

# Update embeddings once
verse-embeddings --multi-collection --collections-file _data/collections.yml
```

## Chapter-Based Collections

For multi-chapter texts (e.g., Bhagavad Gita), use the `--chapter` flag with `verse-add`.

```bash
verse-add --collection bhagavad-gita --verse 1-47 --chapter 1
verse-generate --collection bhagavad-gita --verse chapter-01-shloka-01
```

Full details: `docs/chapter-based-formats.md`

## Theme Customization

Each theme lives in `data/themes/<collection>/<theme>.yml` and defines art direction for image generation. Update these files to control style, palette, and prompts.

```bash
# Generate using a specific theme
verse-generate --collection hanuman-chalisa --verse 1 --theme watercolor-art --image
```

## API Costs

Cost drivers include:
- Image generation (DALL-E)
- Audio generation (ElevenLabs)
- Embeddings (OpenAI/Bedrock/HuggingFace)

Tips to control spend:
- Use `--no-update-embeddings` during iterative content work.
- Batch embeddings at the end with `verse-embeddings`.
- Run audio and images selectively using `verse-audio` and `verse-images`.

## Best Practices

- Keep `_data/collections.yml` as the single source of truth for enabled collections.
- Store canonical text only in `data/verses/<collection>.yaml`.
- Use `verse-validate` before large batch runs.
- Prefer provider-wide defaults in `_data/embeddings.yml` to keep commands clean.
- Commit `data/puranic-index/` and `data/embeddings/puranic/` for reproducible RAG.

## Related Docs

- `docs/end-to-end-workflow.md`
- `docs/commands/verse-validate.md`
- `docs/commands/verse-embeddings.md`
- `docs/embeddings-config.md`
- `docs/troubleshooting.md`
