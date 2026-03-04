# verse-audio

Generate audio pronunciations for verses using ElevenLabs text-to-speech.

## Synopsis

```bash
verse-audio --collection COLLECTION [OPTIONS]
```

## Description

The `verse-audio` command generates pronunciation audio files using ElevenLabs' text-to-speech API. It reads text from the `devanagari:` field in verse markdown files and creates two versions:
- Full speed (normal)
- Slow speed (0.75x for learning pronunciation)

## Options

### Required

- `--collection NAME` - Collection key (e.g., `hanuman-chalisa`, `sundar-kaand`)

### Optional

- `--verse ID` - Generate audio for specific verse only
- `--api-key KEY` - ElevenLabs API key (precedence: `--api-key` > `ELEVENLABS_API_KEY` env > `.env` fallback)
- `--voice-id ID` - ElevenLabs voice ID (default: pre-configured voice)
- `--regenerate FILE[,FILE...]` - Regenerate specific audio files
- `--force` - Regenerate all audio files (prompts for confirmation)
- `--list-collections` - List all available collections

## Examples

### List Available Collections

```bash
verse-audio --list-collections
```

### Generate All Audio for a Collection

```bash
verse-audio --collection hanuman-chalisa
```

Scans `_verses/hanuman-chalisa/` directory and generates audio for all verses that don't have audio files yet.

### Generate Specific Verse

```bash
verse-audio --collection sundar-kaand --verse chaupai_03
```

### Regenerate Specific Files

```bash
# Single file
verse-audio --collection hanuman-chalisa --regenerate verse_01_full.mp3

# Multiple files
verse-audio --collection hanuman-chalisa --regenerate verse_01_full.mp3,verse_01_slow.mp3

# Different collection
verse-audio --collection sundar-kaand --regenerate chaupai_03_full.mp3,chaupai_03_slow.mp3
```

### Force Regenerate All

```bash
verse-audio --collection hanuman-chalisa --force
```

This will prompt for confirmation before regenerating all audio files.

## Generated Files

For each verse, two MP3 files are created in `audio/<collection-key>/`:

- `verse_NN_full.mp3` - Full speed (normal)
- `verse_NN_slow.mp3` - Slow speed (0.75x)

Example paths:
- `audio/hanuman-chalisa/verse_01_full.mp3`
- `audio/hanuman-chalisa/verse_01_slow.mp3`
- `audio/sundar-kaand/chaupai_03_full.mp3`
- `audio/sundar-kaand/chaupai_03_slow.mp3`

## Voice Configuration

The SDK uses a pre-configured voice ID. To use a different voice:

```bash
verse-audio --voice-id YOUR_VOICE_ID
```

Find voice IDs in your ElevenLabs dashboard: https://elevenlabs.io/app/voice-library

## Verse File Format

Audio is generated from the `devanagari:` field in verse files:

```yaml
---
devanagari: |
  धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः।
  मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय।।
---
```

The command reads this field and generates audio pronunciation.

## Workflow

```bash
# 1. Ensure verse files exist with devanagari field
cat _verses/hanuman-chalisa/verse_01.md

# 2. Generate audio
verse-audio --collection hanuman-chalisa

# 3. Verify files
ls -lh audio/hanuman-chalisa/verse_01_*.mp3

# 4. Test audio playback
afplay audio/hanuman-chalisa/verse_01_full.mp3  # macOS
mpg123 audio/hanuman-chalisa/verse_01_full.mp3  # Linux

# 5. Commit
git add audio/
git commit -m "Add audio pronunciations for Hanuman Chalisa"
```

## Cost

ElevenLabs pricing is character-based:
- Verses average ~150-300 characters
- Each verse generates 2 files (full + slow)
- Cost: ~$0.001-0.002 per verse

For 700 verses (complete Bhagavad Gita):
- Total cost: ~$0.70-1.40

Very affordable compared to image generation.

## Performance

- Generation speed: ~2-3 seconds per file
- For 700 verses (1400 files): ~45-60 minutes
- Audio files average 200-400 KB each

## Requirements

- ElevenLabs API key resolution precedence:
  - `--api-key` flag
  - `ELEVENLABS_API_KEY` exported environment variable
  - `.env` fallback (`ELEVENLABS_API_KEY=...`)
- Verse files in `_verses/<collection-key>/` with `devanagari:` field populated
- Collection enabled in `_data/collections.yml`
- ElevenLabs account with sufficient credits

## Notes

- Audio is only generated if files don't already exist (unless using `--regenerate` or `--force`)
- The slow speed version (0.75x) is ideal for learning pronunciation
- Generated files are MP3 format for broad compatibility
- Both EU and US production environments are supported (auto-detected)

## Troubleshooting

### "Error: ELEVENLABS_API_KEY not set"

Set your API key:

```bash
export ELEVENLABS_API_KEY=your_key_here
```

Or add to `.env` file:

```
ELEVENLABS_API_KEY=your_key_here
```

### "Error: No devanagari field found"

Ensure verse file has the `devanagari:` field in frontmatter:

```yaml
---
devanagari: |
  Your verse text in Devanagari script here
---
```

### "Generation failed for some files"

Check:
- ElevenLabs API key is valid
- Account has sufficient credits
- Internet connection is stable

Use `--regenerate` to retry failed files.

## See Also

- [verse-generate](verse-generate.md) - Generate audio automatically with other content
- [ElevenLabs Documentation](https://elevenlabs.io/docs) - API reference
- [Troubleshooting](../troubleshooting.md) - Common issues
