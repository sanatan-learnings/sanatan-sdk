#!/usr/bin/env python3
"""
Project initialization command - scaffolds directory structure for a new verse project.

This command creates the recommended directory structure and template files
for starting a new verse collection project with sanatan-verse-sdk.

Usage:
    # Initialize in current directory
    verse-init

    # Initialize with custom project name
    verse-init --project-name my-verse-project

    # Initialize with example collection
    verse-init --with-example hanuman-chalisa

    # Initialize minimal structure (no examples)
    verse-init --minimal
"""

import argparse
import base64
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

# Template files content
ENV_EXAMPLE_CONTENT = """# OpenAI API Key (for images, embeddings, and content generation)
# Get your key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your_openai_key_here

# ElevenLabs API Key (for audio generation)
# Get your key from: https://elevenlabs.io/app/settings/api-keys
ELEVENLABS_API_KEY=your_elevenlabs_key_here

# Hugging Face token (for gated/model downloads where required)
# Get your token from: https://huggingface.co/settings/tokens
HF_TOKEN=your_huggingface_token_here
"""

COLLECTIONS_YML_CONTENT = """# Collection registry
# Add your verse collections here

# Example:
# hanuman-chalisa:
#   enabled: true
#   name:
#     en: "Hanuman Chalisa"
#     hi: "हनुमान चालीसा"
#   subdirectory: "hanuman-chalisa"
#   permalink_base: "/hanuman-chalisa"
#   total_verses: 43
#   # subject and subject_type are optional here if set in _data/verse-config.yml defaults
#   # subject: Hanuman
#   # subject_type: deity
"""

VERSE_CONFIG_CONTENT = """# Project-level configuration for sanatan-verse-sdk
# These defaults apply to all collections unless overridden at the collection level.

defaults:
  # subject: Hanuman        # primary deity / subject of this project
  # subject_type: deity     # deity | avatar | concept | figure

  # subject and subject_type are used by verse-puranic-context to filter
  # RAG retrieval to episodes where the subject is a direct participant.
  # Collections can override by setting subject / subject_type in collections.yml.
"""

GITIGNORE_CONTENT = """# Generated content
images/
audio/

# Environment
.env
.venv/
venv/
env/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
"""

GEMFILE_CONTENT = """source "https://rubygems.org"

gem "jekyll", "~> 4.3"
gem "webrick", "~> 1.8"
"""

README_TEMPLATE = """# {project_name}

Verse collection project powered by [Sanatan Verse SDK](https://github.com/sanatan-learnings/sanatan-verse-sdk).

## Setup

1. **Install dependencies**
   ```bash
   pip install sanatan-verse-sdk
   ```

2. **Configure API keys**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

3. **Add your collections**
   - Edit `_data/collections.yml` to define your collections
   - Create verse files in `_verses/<collection-key>/`
   - Add canonical text in `data/verses/<collection>.yaml`

4. **Generate content**
   ```bash
   # List available collections
   verse-generate --list-collections

   # Generate multimedia content
   verse-generate --collection <collection-key> --verse 1
   ```

## Project Structure

```
{project_name}/
├── _data/
│   ├── collections.yml          # Collection registry
│   └── verse-config.yml         # Project-level defaults (subject, subject_type)
├── _verses/
│   └── <collection-key>/        # Verse markdown files
├── data/
│   ├── themes/
│   │   └── <collection-key>/    # Theme configurations
│   ├── verses/
│   │   └── <collection>.yaml    # Canonical verse text
│   ├── scenes/                  # Scene descriptions for image generation
│   ├── sources/                 # Source texts for RAG indexing
│   ├── puranic-index/           # Indexed Puranic episodes
│   └── embeddings/              # Vector embeddings
│       └── puranic/             # Puranic source embeddings
├── images/                      # Generated images (gitignored)
├── audio/                       # Generated audio (gitignored)
└── .env                         # API keys (gitignored)
```

## Documentation

- [Usage Guide](https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/usage.md)
- [Commands Reference](https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/README.md)
- [Troubleshooting](https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/troubleshooting.md)

## License

MIT
"""

JEKYLL_CONFIG_TEMPLATE = """title: "{project_name}"
description: "Verse collection project powered by Sanatan Verse SDK"
markdown: kramdown
collections:
  verses:
    output: true
    permalink: /:path/
defaults:
  - scope:
      path: ""
      type: verses
    values:
      layout: verse
exclude:
  - README.md
  - venv/
  - .venv/
"""

DEFAULT_LAYOUT_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ page.title | default: site.title }}</title>
    <style>
      :root {
        --bg: #f6f1e7;
        --text: #1f1a14;
        --accent: #b35c1e;
      }
      body {
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background: linear-gradient(180deg, #fbf8f2 0%, var(--bg) 100%);
        color: var(--text);
      }
      main {
        max-width: 880px;
        margin: 0 auto;
        padding: 2rem 1rem 3rem;
      }
      h1, h2, h3 {
        color: var(--accent);
      }
      a {
        color: var(--accent);
      }
      code {
        background: rgba(0, 0, 0, 0.05);
        border-radius: 4px;
        padding: 0.1rem 0.35rem;
      }
    </style>
  </head>
  <body>
    <main>
      {{ content }}
    </main>
  </body>
</html>
"""

INDEX_MD_TEMPLATE = """---
layout: home
title: __PROJECT_NAME__
---

## Collections

{% assign has_enabled = false %}
{% for pair in site.data.collections %}
  {% assign cfg = pair[1] %}
  {% if cfg.enabled %}
    {% assign has_enabled = true %}
  {% endif %}
{% endfor %}

{% if has_enabled %}
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;">
{% for pair in site.data.collections %}
  {% assign key = pair[0] %}
  {% assign cfg = pair[1] %}
  {% unless cfg.enabled %}{% continue %}{% endunless %}
  <a href="/{{ key }}/" style="display:block;text-decoration:none;color:inherit;border:1px solid #e4d8c2;border-radius:12px;padding:1rem;background:#fffdf8;">
    <img src="/images/{{ key }}/modern-minimalist/card-page.png" onerror="this.onerror=null;this.src='/images/{{ key }}/card.png';" alt="{{ cfg.name.en | default: key }} card image" style="width:100%;height:auto;border-radius:10px;border:1px solid #ead8bc;margin-bottom:0.75rem;" />
    <div style="font-size:1.1rem;font-weight:700;">{{ cfg.name.en | default: key }}</div>
    {% if cfg.name.hi %}<div style="opacity:0.85;margin-top:0.3rem;">{{ cfg.name.hi }}</div>{% endif %}
    <div style="margin-top:0.6rem;font-size:0.9rem;">{{ cfg.total_verses | default: 0 }} verses</div>
  </a>
{% endfor %}
</div>
{% else %}
No enabled collections found in `_data/collections.yml`.
{% endif %}
"""

HOME_LAYOUT_TEMPLATE = """---
layout: default
---

<h1>{{ page.title | default: site.title }}</h1>
<p>{{ site.description }}</p>

{{ content }}
"""

COLLECTION_LAYOUT_TEMPLATE = """---
layout: default
---

{% assign collection_key = page.collection_key | default: page.slug %}
{% assign collection_cfg = site.data.collections[collection_key] %}

<h1>{{ collection_cfg.name.en | default: collection_key }}</h1>
{% if collection_cfg.name.hi %}<p style="font-size:1.1rem;">{{ collection_cfg.name.hi }}</p>{% endif %}

<img src="/images/{{ collection_key }}/modern-minimalist/title-page.png" onerror="this.onerror=null;this.src='/images/{{ collection_key }}/title.png';" alt="{{ collection_cfg.name.en | default: collection_key }} title" style="width:100%;max-width:960px;height:auto;border-radius:12px;border:1px solid #e4d8c2;background:#fffdf8;" />

{% assign verse_count = 0 %}
{% for verse in site.verses %}
  {% if verse.collection_key == collection_key %}
    {% assign verse_count = verse_count | plus: 1 %}
  {% endif %}
{% endfor %}
<p>Total verses: {{ collection_cfg.total_verses | default: verse_count }}</p>

<ul>
{% assign listed = false %}
{% for verse in site.verses %}
  {% if verse.collection_key == collection_key %}
    {% assign listed = true %}
  <li>
    <a href="{{ verse.url }}">{{ verse.verse_id | default: verse.title | default: verse.basename }}</a>
  </li>
  {% endif %}
{% endfor %}
{% unless listed %}
  <li>No verses generated yet for this collection.</li>
{% endunless %}
</ul>
"""

VERSE_LAYOUT_TEMPLATE = """---
layout: default
---

<h1>{{ page.title | default: page.verse_id | default: page.basename }}</h1>
{% if page.verse_number %}<p>Verse {{ page.verse_number }}</p>{% endif %}

{% assign auto_image = '/images/' | append: page.collection | append: '/' | append: page.verse_id | append: '.png' %}
<img src="{{ page.image | default: auto_image }}" alt="{{ page.title | default: page.verse_id }}" style="max-width:100%;height:auto;border-radius:10px;" />

{% if page.audio %}
<audio controls style="width:100%;margin-top:1rem;">
  <source src="{{ page.audio }}" />
</audio>
{% endif %}

{{ content }}
"""

COLLECTION_INDEX_TEMPLATE = """---
layout: collection
title: {display_name}
collection_key: {collection_key}
---
"""

PNG_PLACEHOLDER_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
)

EXAMPLE_THEME_YML = """name: Modern Minimalist
description: Clean, minimal design with spiritual focus

theme:
  generation:
    style_modifier: |
      Style: Modern minimalist Indian devotional art. Clean composition with balanced negative space.
      Soft, warm color palette featuring deep saffron, spiritual blue, gentle gold accents, and cream tones.
      Simplified forms with spiritual elegance. Subtle divine glow and ethereal lighting.
      Contemporary interpretation of traditional Indian spiritual art.
      Portrait orientation (1024x1792), will be cropped to 1024x1536 for final display.

# Image generation settings
size: "1024x1792"        # Portrait format (recommended)
quality: "standard"      # Options: standard ($0.04), hd ($0.08)
style: "natural"         # Options: natural, vivid
"""


def create_directory_structure(base_path: Path, minimal: bool = False) -> None:
    """
    Create the recommended directory structure.

    Args:
        base_path: Base directory path
        minimal: If True, create minimal structure without example files
    """
    # Required directories
    directories = [
        "_data",
        "_layouts",
        "_verses",
        "data/themes",
        "data/verses",
        "data/scenes",
    ]

    # Optional directories (created automatically by commands, but good to have)
    if not minimal:
        directories.extend([
            "images",
            "audio",
            "data/sources",
            "data/puranic-index",
            "data/embeddings",
        ])

    for dir_path in directories:
        full_path = base_path / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {dir_path}/")


def create_template_files(base_path: Path, project_name: str, minimal: bool = False) -> None:
    """
    Create template configuration files.

    Args:
        base_path: Base directory path
        project_name: Project name for templates
        minimal: If True, create minimal files only
    """
    # Always create these files
    files = {
        ".env.example": ENV_EXAMPLE_CONTENT,
        "_data/collections.yml": COLLECTIONS_YML_CONTENT,
        "_data/verse-config.yml": VERSE_CONFIG_CONTENT,
        ".gitignore": GITIGNORE_CONTENT,
        "Gemfile": GEMFILE_CONTENT,
        "_config.yml": JEKYLL_CONFIG_TEMPLATE.format(project_name=project_name),
        "_layouts/default.html": DEFAULT_LAYOUT_TEMPLATE,
        "_layouts/home.html": HOME_LAYOUT_TEMPLATE,
        "_layouts/collection.html": COLLECTION_LAYOUT_TEMPLATE,
        "_layouts/verse.html": VERSE_LAYOUT_TEMPLATE,
        "index.md": INDEX_MD_TEMPLATE.replace("__PROJECT_NAME__", project_name),
        "README.md": README_TEMPLATE.format(project_name=project_name),
    }

    # Add example theme if not minimal
    if not minimal:
        files["data/themes/.gitkeep"] = "# Theme files go in subdirectories by collection\n# Example: data/themes/hanuman-chalisa/modern-minimalist.yml\n"

    for file_path, content in files.items():
        full_path = base_path / file_path
        if not full_path.exists():
            full_path.write_text(content)
            print(f"✓ Created {file_path}")
        else:
            print(f"⚠ Skipped {file_path} (already exists)")


def to_hindi_name(collection: str) -> str:
    """Best-effort Hindi/Sanskrit name for a collection key."""
    mapping = {
        "hanuman": "हनुमान",
        "chalisa": "चालीसा",
        "sundar": "सुंदर",
        "kaand": "काण्ड",
        "kand": "काण्ड",
        "shiv": "शिव",
        "shiva": "शिव",
        "puran": "पुराण",
        "puranam": "पुराण",
        "ram": "राम",
        "rama": "राम",
        "gita": "गीता",
        "bhagavad": "भगवद",
        "bhagavat": "भागवत",
        "krishna": "कृष्ण",
    }
    words = collection.replace("_", "-").split("-")
    converted = [mapping.get(word.lower(), word.title()) for word in words if word]
    return " ".join(converted) if converted else collection


def upsert_collection_entry(content: str, collection: str, num_verses: int) -> str:
    """Insert collection entry before commented example block in collections.yml."""
    if re.search(rf"^{re.escape(collection)}:\s*$", content, flags=re.MULTILINE):
        return content

    display_name = collection.replace("-", " ").title()
    hi_name = to_hindi_name(collection)
    entry = (
        f"{collection}:\n"
        "  enabled: true\n"
        "  name:\n"
        f"    en: \"{display_name}\"\n"
        f"    hi: \"{hi_name}\"\n"
        f"  subdirectory: \"{collection}\"\n"
        f"  permalink_base: \"/{collection}\"\n"
        f"  total_verses: {num_verses}\n"
    )

    marker = "\n# Example:"
    if marker in content:
        before, after = content.split(marker, 1)
        before = before.rstrip() + "\n\n"
        return before + entry + marker + after

    content = content.rstrip() + "\n\n"
    return content + entry


def create_collection_image_placeholders(base_path: Path, collection: str) -> None:
    """Create deterministic PNG placeholders in images/<collection>/."""
    images_dir = base_path / "images" / collection
    images_dir.mkdir(parents=True, exist_ok=True)
    placeholder_bytes = base64.b64decode(PNG_PLACEHOLDER_BASE64)

    card_image = images_dir / "card.png"
    if not card_image.exists():
        card_image.write_bytes(placeholder_bytes)
        print(f"✓ Created images/{collection}/card.png")

    title_image = images_dir / "title.png"
    if not title_image.exists():
        title_image.write_bytes(placeholder_bytes)
        print(f"✓ Created images/{collection}/title.png")


def create_example_collection(base_path: Path, collection: str, num_verses: int = 3) -> None:
    """
    Create an example collection with sample files.

    Args:
        base_path: Base directory path
        collection: Collection name (e.g., 'hanuman-chalisa')
        num_verses: Number of sample verses to create (default: 3)
    """
    print(f"\nCreating collection: {collection}")
    print("-" * 50)

    # Create collection directory
    collection_dir = base_path / "_verses" / collection
    collection_dir.mkdir(parents=True, exist_ok=True)

    # Create canonical verse YAML file
    verses_yaml = base_path / "data" / "verses" / f"{collection}.yaml"
    verses_yaml.parent.mkdir(parents=True, exist_ok=True)
    if not verses_yaml.exists():
        yaml_content = f"""# Canonical verse text for {collection}
# This is the authoritative source for Devanagari text

_meta:
  collection: {collection}
  source: "[Add source URL here]"
  description: "{collection.replace('-', ' ').title()}"

  # Optional: Define reading sequence for ordered playback
  sequence:
"""
        for i in range(1, num_verses + 1):
            yaml_content += f"    - verse-{i:02d}\n"

        yaml_content += """
# Add your verses here with canonical Devanagari text
# Format 1: Dict with devanagari field (recommended for extensibility)
verse-01:
  devanagari: "[Add canonical Devanagari text here]"

verse-02:
  devanagari: "[Add canonical Devanagari text here]"

verse-03:
  devanagari: "[Add canonical Devanagari text here]"

# Format 2: Simple string (more concise)
# verse-01: "Devanagari text here"
"""
        verses_yaml.write_text(yaml_content)
        print(f"✓ Created data/verses/{collection}.yaml")

    # Create sample theme
    theme_file = base_path / "data" / "themes" / collection / "modern-minimalist.yml"
    theme_file.parent.mkdir(parents=True, exist_ok=True)
    if not theme_file.exists():
        theme_file.write_text(EXAMPLE_THEME_YML)
        print(f"✓ Created data/themes/{collection}/modern-minimalist.yml")

    # Create minimal scene descriptions file (YAML format in data/scenes/)
    scenes_file = base_path / "data" / "scenes" / f"{collection}.yml"
    scenes_file.parent.mkdir(parents=True, exist_ok=True)
    if not scenes_file.exists():
        scenes_content = f"""_meta:
  collection: {collection}
  description: Scene descriptions for {collection.replace('-', ' ').title()} image generation

scenes:
  title-page:
    title: "{collection.replace('-', ' ').title()} Title Page"
    description: |
      Close-up portrait of the primary deity/subject filling the lower two-thirds of the frame.
      Crowned head, serene yet powerful face, and upper chest centered in composition.
      Upper third shows radiant sky with golden divine light and subtle sacred patterns.
      Use saffron, gold, and spiritual blue tones with devotional atmosphere.
  card-page:
    title: "{collection.replace('-', ' ').title()} Card Image"
    description: |
      A clean, iconic devotional composition for collection listing cards.
      Focus on symbolic visual elements associated with the collection subject.
      Balanced framing suitable for landscape card display, warm saffron-gold palette,
      and clear contrast for title text overlay if needed.
"""
        scenes_file.write_text(scenes_content)
        print(f"✓ Created data/scenes/{collection}.yml")

    # Create canonical plain-text source placeholder for parse-source auto-discovery
    source_file = base_path / "data" / "sources" / f"{collection}.txt"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    if not source_file.exists():
        source_content = f"""# Source text for {collection}
# Paste canonical plain-text verses here (UTF-8).
# Then run:
#   verse-parse-source --collection {collection}
"""
        source_file.write_text(source_content)
        print(f"✓ Created data/sources/{collection}.txt")

    # Update collections.yml
    collections_file = base_path / "_data" / "collections.yml"
    if collections_file.exists():
        content = collections_file.read_text(encoding="utf-8")
        updated = upsert_collection_entry(content, collection, num_verses)
        if updated != content:
            collections_file.write_text(updated, encoding="utf-8")
            print(f"✓ Added {collection} to _data/collections.yml")

    # Create deterministic placeholder image assets for card and title contexts.
    create_collection_image_placeholders(base_path, collection)

    # Create collection landing page for local Jekyll preview.
    collection_page = base_path / collection / "index.md"
    collection_page.parent.mkdir(parents=True, exist_ok=True)
    if not collection_page.exists():
        display_name = collection.replace("-", " ").title()
        collection_page.write_text(
            COLLECTION_INDEX_TEMPLATE.format(display_name=display_name, collection_key=collection),
            encoding="utf-8"
        )
        print(f"✓ Created {collection}/index.md")

    print(f"\n✅ Collection '{collection}' initialized (canonical placeholders: {num_verses})")


def print_collection_next_steps(collection: str, num_verses: int, additional_collections: int = 0) -> None:
    """Print consolidated next steps for initialized collections."""
    print("📝 Next steps:")
    print("   1. Configure environment before generation:")
    print("      cp .env.example .env")
    print("      Set OPENAI_API_KEY (and ELEVENLABS_API_KEY if generating audio)")
    print("   2. Add canonical source text (plain text), either:")
    print(f"      - Directory mode: data/sources/{collection}/...")
    print(f"      - Single-file mode: data/sources/{collection}.txt")
    print("   3. Generate canonical YAML from source text:")
    print(f"      verse-parse-source --collection {collection}")
    print(f"      Output: data/verses/{collection}.yaml")
    print(f"      (Optional fallback: edit data/verses/{collection}.yaml manually)")
    print(f"   4. Optional: customize theme in data/themes/{collection}/modern-minimalist.yml")
    print("   5. Generate first verse content + assets from canonical YAML:")
    print(f"      verse-generate --collection {collection} --verse 1")
    print("      (Scene descriptions can be auto-generated by verse-generate, or edited in data/scenes manually.)")
    print("      Optional scene-driven collection images from data/scenes:")
    print(f"      verse-images --collection {collection} --theme modern-minimalist --verse title-page")
    print(f"      verse-images --collection {collection} --theme modern-minimalist --verse card-page")
    print(f"      Outputs: images/{collection}/modern-minimalist/title-page.png and card-page.png")
    print(f"   6. Review/edit generated verses in _verses/{collection}/ for quality")
    print("   7. Preview locally and verify output:")
    print("      bundle install")
    print("      bundle exec jekyll serve")
    print("   8. Optional next: generate full collection:")
    print(f"      verse-generate --collection {collection} --all")
    print(f"      # or explicit range: verse-generate --collection {collection} --verse 1-{num_verses}")
    print(f"      # or iterative: verse-generate --collection {collection} --next")
    print("   9. Optional quality check: verse-validate")
    print("   10. Optional advanced workflows: verse-embeddings / verse-index-sources / verse-puranic-context / verse-deploy")
    print("   11. Docs for advanced workflows: https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/usage.md")
    if additional_collections > 0:
        print(f"   12. Repeat steps 2-11 for the other {additional_collections} collection(s).")


def print_generic_next_steps() -> None:
    """Print next steps when no collection templates were created."""
    print("📝 Next steps:")
    print("   1. Copy .env.example to .env and add your API keys")
    print("   2. Edit _data/collections.yml to define your collections")
    print("   3. Add canonical verse text to data/verses/<collection>.yaml")
    print("   4. Run: verse-validate")


def init_project(
    project_name: Optional[str] = None,
    minimal: bool = False,
    collections: Optional[List[str]] = None,
    num_verses: int = 3
) -> None:
    """
    Initialize a new verse project.

    Args:
        project_name: Name for the project (creates subdirectory if provided)
        minimal: Create minimal structure without examples
        collections: List of collection names to create
        num_verses: Number of sample verses per collection (default: 3)
    """
    # Determine base path
    if project_name:
        base_path = Path.cwd() / project_name
        if base_path.exists():
            print(f"Error: Directory '{project_name}' already exists")
            sys.exit(1)
        base_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 Initializing project in: {base_path}")
    else:
        base_path = Path.cwd()
        # Check if directory is empty (excluding hidden files)
        if any(base_path.iterdir()):
            response = input("⚠️  Current directory is not empty. Continue? [y/N] ")
            if response.lower() != 'y':
                print("Aborted.")
                sys.exit(0)
        print("📁 Initializing project in current directory")

    print()

    # Create structure
    print("Creating directory structure...")
    create_directory_structure(base_path, minimal)
    print()

    # Create template files
    print("Creating template files...")
    display_name = project_name if project_name else base_path.name
    create_template_files(base_path, display_name, minimal)
    print()

    # Create collections if requested
    if collections:
        print()
        print("=" * 70)
        print("Creating Collections")
        print("=" * 70)
        for collection in collections:
            create_example_collection(base_path, collection, num_verses)

    # Success message
    print()
    print("=" * 70)
    print("✅ Project initialized successfully!")
    print("=" * 70)
    print()
    if collections:
        primary_collection = collections[0]
        print_collection_next_steps(
            collection=primary_collection,
            num_verses=num_verses,
            additional_collections=max(0, len(collections) - 1)
        )
    else:
        print_generic_next_steps()
    print()
    print("📚 Documentation: https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/usage.md")
    print()


def main():
    """Main entry point for verse-init command."""
    parser = argparse.ArgumentParser(
        description="Initialize a new verse project with recommended structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize in current directory
  verse-init

  # Create new project directory
  verse-init --project-name my-verse-project

  # Initialize with one collection
  verse-init --collection hanuman-chalisa

  # Initialize with multiple collections
  verse-init --collection hanuman-chalisa --collection sundar-kaand

  # Specify number of sample verses
  verse-init --collection my-collection --num-verses 5

  # Complete setup
  verse-init --project-name my-project --collection hanuman-chalisa --num-verses 10

  # Minimal structure (no examples)
  verse-init --minimal

For more information:
  https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/usage.md
        """
    )

    parser.add_argument(
        "--project-name",
        help="Project name (creates subdirectory)"
    )

    parser.add_argument(
        "--collection",
        action="append",
        dest="collections",
        metavar="NAME",
        help="Create collection with template files (can be used multiple times)"
    )

    parser.add_argument(
        "--num-verses",
        type=int,
        default=3,
        metavar="N",
        help="Number of sample verses to create per collection (default: 3)"
    )

    parser.add_argument(
        "--with-example",
        metavar="COLLECTION",
        help="[Deprecated] Use --collection instead"
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Create minimal structure without example files"
    )

    args = parser.parse_args()

    # Handle deprecated --with-example flag
    collections = args.collections or []
    if args.with_example:
        print("⚠️  Note: --with-example is deprecated, use --collection instead")
        collections.append(args.with_example)

    try:
        init_project(
            project_name=args.project_name,
            minimal=args.minimal,
            collections=collections if collections else None,
            num_verses=args.num_verses
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
