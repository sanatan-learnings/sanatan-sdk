# End-to-End Workflow

This guide walks through the full lifecycle: initialize a project, add canonical text, generate assets, build embeddings, optionally index sources for Puranic context, and deploy the API proxy.

## 1. Install

```bash
pip install sanatan-verse-sdk
```

## 2. Initialize Project

```bash
verse-init --project-name my-verse-project --collection hanuman-chalisa
cd my-verse-project
```

### Directory Structure (Key Paths)

```
your-project/
├── .env                                  # API keys
├── _data/collections.yml                 # Collection registry
├── _verses/<collection>/                 # Verse markdown files
├── data/verses/<collection>.yaml         # Canonical Devanagari text
├── data/themes/<collection>/             # Theme configs
├── data/scenes/<collection>.md           # Scene descriptions
├── data/embeddings/collections/          # Verse embeddings + index.json
├── data/embeddings/puranic/              # Puranic source embeddings
├── data/puranic-index/                   # Puranic episode index
├── images/<collection>/<theme>/          # Generated images
└── audio/<collection>/                   # Generated audio
```

## 3. Configure API Keys

```bash
cp .env.example .env
# Edit .env and add your API keys:
# - OpenAI
# - ElevenLabs
```

## 4. Add Canonical Text

Edit `data/verses/<collection>.yaml` and add the Devanagari text for each verse. See `docs/local-verses.md` for the YAML format.

## 5. Validate

```bash
verse-validate
```

## 6. Generate Core Assets

```bash
verse-generate --collection hanuman-chalisa --verse 1
```

Outputs:
- Images: `images/<collection>/<theme>/verse-01.png`
- Audio: `audio/<collection>/verse-01-full.mp3` and `audio/<collection>/verse-01-slow.mp3`
- Embeddings: `data/embeddings/collections/<collection>.json` + `index.json`

## 7. Embeddings (Optional Batch Refresh)

Single collection:
```bash
verse-embeddings --collection hanuman-chalisa --collections-file _data/collections.yml
```

Multiple collections:
```bash
verse-embeddings --multi-collection --collections-file _data/collections.yml
```

For shared defaults, see `docs/embeddings-config.md`.

## 8. Puranic Context (Optional)

Index a source text once:
```bash
verse-index-sources --file data/sources/valmiki-ramayana.pdf
```

Generate context for all verses:
```bash
verse-puranic-context --collection hanuman-chalisa --all
```

Architecture details: `docs/puranic-context-architecture.md`

## 9. Deploy API Proxy

Deploy the API proxy used by your frontend or apps:
```bash
verse-deploy
```

This sets up a Cloudflare Worker, stores `OPENAI_API_KEY` as a secret, and returns a worker URL. For deployment details, see `docs/commands/verse-deploy.md`.

## 10. Post-Deploy

- Update your frontend client to call the worker URL.
- Tail logs with `wrangler tail`.

## References

- `docs/commands/verse-init.md`
- `docs/commands/verse-generate.md`
- `docs/commands/verse-embeddings.md`
- `docs/commands/verse-index-sources.md`
- `docs/commands/verse-puranic-context.md`
- `docs/commands/verse-deploy.md`
- `docs/troubleshooting.md`
