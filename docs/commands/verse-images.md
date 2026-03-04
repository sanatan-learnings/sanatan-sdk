# verse-images

Generate images for verses using DALL-E 3 based on scene descriptions.

## Synopsis

```bash
verse-images [--collection COLLECTION] [--theme THEME] [OPTIONS]
```

## Description

The `verse-images` command generates artwork for verses using OpenAI's DALL-E 3 API. It reads scene descriptions from `data/scenes/<collection-key>.yml` and creates images styled according to a theme configuration.

## Options

### Collection and Theme Selection

- `--collection NAME` - Collection key (e.g., `hanuman-chalisa`, `sundar-kaand`)
- `--theme NAME` - Theme name (must have corresponding `data/themes/<collection-key>/<theme-name>.yml`)

`--collection` and `--theme` are optional when unambiguous:

- If exactly one collection exists/enabled, `verse-images` auto-selects it.
- If exactly one theme exists for the collection (or a single configured default theme is set), `verse-images` auto-selects it.
- If multiple choices exist, command exits with a clear error listing choices and asks for explicit flags.

### Optional

- `--verse ID` - Generate image for specific verse only
- `--regenerate FILE[,FILE...]` - Regenerate specific image files
- `--force` - Regenerate all images (prompts for confirmation)
- `--list-collections` - List all available collections

## Examples

### List Available Collections

```bash
verse-images --list-collections
```

### Generate All Images for a Collection

```bash
verse-images --collection hanuman-chalisa --theme modern-minimalist
```

This reads all scene descriptions from `data/scenes/hanuman-chalisa.md` and generates images that don't already exist.
This reads all scene descriptions from `data/scenes/hanuman-chalisa.yml` and generates images that don't already exist.

### Generate with Auto-Selection (Single Collection + Theme)

```bash
verse-images --verse title-page
```

Works when collection and theme are unambiguous in project config/files.

### Generate Specific Verse

```bash
verse-images --collection sundar-kaand --theme modern-minimalist --verse chaupai_03
```

### Regenerate Specific Images

```bash
# Single image
verse-images --collection hanuman-chalisa --theme kids-friendly --regenerate verse-15.png

# Multiple images
verse-images --collection hanuman-chalisa --theme modern-minimalist \
  --regenerate verse-01.png,verse-02.png
```

### Force Regenerate All

```bash
verse-images --collection hanuman-chalisa --theme modern-minimalist --force
```

This will prompt for confirmation before regenerating all images.

## Theme Configuration

Themes are defined per collection in `data/themes/<collection-key>/<theme-name>.yml`:

```yaml
name: modern-minimalist
description: Modern minimalist Indian devotional art

style_modifier: |
  Style: Modern minimalist Indian devotional art. Clean composition with balanced negative space.
  Soft, warm color palette featuring deep saffron, spiritual blue, gentle gold accents, and cream tones.
  Simplified forms with spiritual elegance. Subtle divine glow and ethereal lighting.
  Contemporary interpretation of traditional Indian spiritual art.
  Portrait orientation (1024x1792), will be cropped to 1024x1536 for final display.

size: 1024x1792        # Portrait format
quality: standard      # Options: standard, hd
style: natural         # Options: natural, vivid
```

Example paths:
- `data/themes/hanuman-chalisa/modern-minimalist.yml`
- `data/themes/sundar-kaand/kids-friendly.yml`

### Theme Options

- **size**: Image dimensions
  - `1024x1024` - Square
  - `1024x1792` - Portrait (recommended)
  - `1792x1024` - Landscape

- **quality**: Image quality
  - `standard` - $0.04 per image
  - `hd` - $0.08 per image, more details

- **style**: Rendering style
  - `natural` - More realistic, balanced
  - `vivid` - More vibrant colors, dramatic

## Scene Descriptions

Scene descriptions are stored per collection in `data/scenes/<collection-key>.yml`:

```yaml
scenes:
  verse-01:
    title: Verse 1
    description: |
      Lord Hanuman standing majestically at the entrance of a serene temple, bathed
      in the golden light of dawn. His form radiates divine energy with a gentle
      glow surrounding him. He holds a gada (mace) in one hand while the other is
      raised in blessing.
```

Example paths:
- `data/scenes/hanuman-chalisa.yml`
- `data/scenes/sundar-kaand.yml`

### Writing Good Scene Descriptions

- **Length**: 3-5 sentences
- **Details**: Include setting, characters, poses, expressions, clothing, colors
- **Lighting**: Specify mood lighting (golden hour, ethereal glow, dramatic)
- **Balance**: Mix realistic and symbolic/spiritual elements
- **Concrete**: Use visual metaphors, avoid abstract concepts

## Generated Files

Images are saved to: `images/<collection-key>/<theme-name>/verse-NN.png`

Format:
- Portrait: 1024x1792 (recommended for mobile/web display)
- Quality: Standard or HD based on theme config
- Format: PNG

Example paths:
- `images/hanuman-chalisa/modern-minimalist/verse-01.png`
- `images/sundar-kaand/kids-friendly/chaupai_03.png`

## Workflow

```bash
# 1. Create theme configuration for a collection
mkdir -p data/themes/hanuman-chalisa
cat > data/themes/hanuman-chalisa/mystical-art.yml << EOF
name: mystical-art
style_modifier: |
  Mystical spiritual art with ethereal lighting...
size: 1024x1792
quality: standard
style: natural
EOF

# 2. Add scene descriptions to data/scenes/hanuman-chalisa.yml
# (Must be created manually with scene descriptions for each verse)

# 3. Generate images
verse-images --collection hanuman-chalisa --theme mystical-art

# 4. Review images
open images/hanuman-chalisa/mystical-art/

# 5. Regenerate specific images if needed
verse-images --collection hanuman-chalisa --theme mystical-art --regenerate verse-05.png
```

## Cost

- **Standard quality**: $0.04 per image
- **HD quality**: $0.08 per image

For 700 verses (complete Bhagavad Gita):
- Standard: ~$28
- HD: ~$56

## Requirements

- `OPENAI_API_KEY` environment variable
- Scene descriptions in `data/scenes/<collection-key>.yml`
- Theme configuration in `data/themes/<collection-key>/<theme-name>.yml`
- Collection enabled in `_data/collections.yml`

## Notes

- Images are only generated if they don't already exist (unless using `--regenerate` or `--force`)
- Generation takes ~10-15 seconds per image
- DALL-E 3 works best with detailed, concrete visual descriptions
- Portrait orientation (1024x1792) works well for mobile and web display

## See Also

- [verse-generate](verse-generate.md) - Generate scene descriptions automatically
- [Troubleshooting](../troubleshooting.md) - Common issues
