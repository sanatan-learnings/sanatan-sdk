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

import yaml

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
gem "jekyll-seo-tag", "~> 2.8"
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
banner_title: "{project_name}"
banner_subtitle: "Verse collection project powered by Sanatan Verse SDK"
markdown: kramdown
collections:
  verses:
    output: true
    permalink: /:path/
plugins:
  - jekyll-seo-tag
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
    <link rel="stylesheet" href="{{ '/assets/css/style.css' | relative_url }}">
    <link rel="stylesheet" href="{{ '/assets/css/print.css' | relative_url }}" media="print">
    {% seo %}
  </head>
  <body>
    <header>
      <div class="container">
        <div class="header-content">
          <div class="header-title">
            <h1><a href="{{ '/' | relative_url }}">{{ site.banner_title | default: site.title }}</a></h1>
            <p class="subtitle">{{ site.banner_subtitle | default: site.description }}</p>
          </div>
          <div class="header-controls">
            <div class="language-switcher">
              <label for="languageSelect" class="sr-only">Language</label>
              <select id="languageSelect" onchange="switchLanguage(this.value)">
                <option value="en">🌐 English</option>
                <option value="hi">🌐 हिन्दी</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </header>
    <main class="container">
      {{ content }}
    </main>
    <script src="{{ '/assets/js/navigation.js' | relative_url }}"></script>
    <script src="{{ '/assets/js/language.js' | relative_url }}"></script>
    <script src="{{ '/assets/js/theme.js' | relative_url }}"></script>
    <script src="{{ '/assets/js/guidance.js' | relative_url }}"></script>
  </body>
</html>
"""

INDEX_HTML_TEMPLATE = """---
layout: home
title: __PROJECT_NAME__
---

{% assign has_enabled = false %}
{% for pair in site.data.collections %}
  {% assign cfg = pair[1] %}
  {% if cfg.enabled %}
    {% assign has_enabled = true %}
  {% endif %}
{% endfor %}

<section class="collections-section">
  <h2><span data-lang="en">{{ site.data.translations.en.home.sacred_text | default: "Sacred Text" }}</span><span data-lang="hi">{{ site.data.translations.hi.home.sacred_text | default: "पवित्र ग्रंथ" }}</span></h2>
{% if has_enabled %}
<div class="collections-grid card-grid">
{% for pair in site.data.collections %}
  {% assign key = pair[0] %}
  {% assign cfg = pair[1] %}
  {% unless cfg.enabled %}{% continue %}{% endunless %}
  <a class="collection-card card" href="/{{ key }}/">
    <img src="/images/{{ key }}/modern-minimalist/card-page.png" alt="{{ cfg.name.en | default: key }} card image" />
    <div class="card-title">{{ cfg.name.en | default: key }}</div>
    {% if cfg.name.hi %}<div class="card-subtitle">{{ cfg.name.hi }}</div>{% endif %}
    <div class="card-subtitle">{{ cfg.total_verses | default: 0 }} verses</div>
  </a>
{% endfor %}
</div>
{% else %}
No enabled collections found in `_data/collections.yml`.
{% endif %}
</section>
"""

HOME_LAYOUT_TEMPLATE = """---
layout: default
---

{{ content }}
"""

COLLECTION_LAYOUT_TEMPLATE = """---
layout: default
---

{% assign collection_key = page.collection_key | default: page.slug %}
{% assign collection_cfg = site.data.collections[collection_key] %}

<h1>{{ collection_cfg.name.en | default: collection_key }}</h1>
{% if collection_cfg.name.hi %}<p>{{ collection_cfg.name.hi }}</p>{% endif %}

<img class="collection-hero-image" src="/images/{{ collection_key }}/modern-minimalist/title-page.png" alt="{{ collection_cfg.name.en | default: collection_key }} title" />

{% assign verse_count = 0 %}
{% for verse in site.verses %}
  {% if verse.collection_key == collection_key %}
    {% assign verse_count = verse_count | plus: 1 %}
  {% endif %}
{% endfor %}
<p>Total verses: {{ collection_cfg.total_verses | default: verse_count }}</p>
<div class="button-row">
  <a class="button" href="/">Back to Home</a>
  <a class="button secondary" href="https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/end-to-end-workflow.md">Workflow Guide</a>
</div>

<ul class="verse-list">
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

<section class="hero">
  <h2>{display_name}</h2>
  <p>Use this page to review generated verses, title/card images, and collection metadata.</p>
</section>
"""

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

STYLE_CSS_TEMPLATE = """:root {
  --bg: #f7f3ea;
  --surface: #fffaf0;
  --surface-strong: #fffdf8;
  --text: #1f1a14;
  --muted: #5f5243;
  --accent: #b35c1e;
  --accent-soft: #f6e2c5;
  --border: #e4d8c2;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Georgia, "Times New Roman", serif;
  background: radial-gradient(circle at top, #fff7ea 0%, var(--bg) 45%, #f0e8dc 100%);
  color: var(--text);
  line-height: 1.6;
}
header {
  border-bottom: 1px solid var(--border);
  background: rgba(255, 250, 240, 0.88);
  backdrop-filter: blur(4px);
}
.container {
  max-width: 1080px;
  margin: 0 auto;
}
.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.9rem 1rem;
}
.header-title h1 {
  margin: 0;
}
.header-title h1 a {
  display: inline-block;
  text-decoration: none;
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--accent);
}
.subtitle {
  color: var(--muted);
  margin-top: 0.2rem;
  margin-bottom: 0;
}
.header-controls {
  display: flex;
  align-items: center;
}
main.container {
  max-width: 1080px;
  margin: 0 auto;
  padding: 2rem 1rem 4rem;
}
h1, h2, h3 { color: var(--accent); }
h1 { margin-top: 0; }
a {
  color: var(--accent);
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
}
code {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
}
.hero {
  border: 1px solid var(--border);
  border-radius: 16px;
  background: linear-gradient(165deg, #fffdf8 0%, #fff6e7 70%, #ffe9cc 100%);
  padding: 1.5rem;
  box-shadow: 0 10px 28px rgba(82, 52, 22, 0.08);
}
.hero p {
  color: var(--muted);
  margin-bottom: 0;
}
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  margin-top: 1rem;
}
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff7ec;
  text-decoration: none;
  border-radius: 999px;
  padding: 0.5rem 1rem;
  font-size: 0.95rem;
}
.button.secondary {
  background: var(--accent-soft);
  color: #7a4214;
  border-color: #d3aa74;
}
.card-grid,
.collections-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin-top: 1.2rem;
}
.card,
.collection-card {
  display: block;
  text-decoration: none;
  color: inherit;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface-strong);
  padding: 0.9rem;
  box-shadow: 0 8px 18px rgba(61, 39, 16, 0.05);
}
.card img,
.collection-card img {
  width: 100%;
  height: auto;
  border-radius: 10px;
  border: 1px solid #ead8bc;
  margin-bottom: 0.75rem;
}
.card-title {
  font-size: 1.05rem;
  font-weight: 700;
}
.card-subtitle {
  opacity: 0.85;
  margin-top: 0.25rem;
}
.collection-hero-image {
  width: 100%;
  max-width: 960px;
  height: auto;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-strong);
}
.verse-list {
  list-style: none;
  padding: 0;
  margin: 1rem 0 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.7rem;
}
.verse-list li a {
  display: block;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-strong);
  padding: 0.6rem 0.8rem;
  text-decoration: none;
}
"""

PRINT_CSS_TEMPLATE = """main.container {
  max-width: none;
  padding: 0;
}
header,
.language-switcher {
  display: none !important;
}
"""

NAVIGATION_JS_TEMPLATE = """// Navigation hooks placeholder for scaffold parity.
"""

LANGUAGE_JS_TEMPLATE = """function switchLanguage(lang) {
  document.documentElement.setAttribute("lang", lang);
  const enNodes = document.querySelectorAll('[data-lang="en"]');
  const hiNodes = document.querySelectorAll('[data-lang="hi"]');
  enNodes.forEach((n) => { n.style.display = lang === "en" ? "" : "none"; });
  hiNodes.forEach((n) => { n.style.display = lang === "hi" ? "" : "none"; });
  localStorage.setItem("site-language", lang);
}

document.addEventListener("DOMContentLoaded", () => {
  const lang = localStorage.getItem("site-language") || "en";
  const select = document.getElementById("languageSelect");
  if (select) select.value = lang;
  switchLanguage(lang);
});
"""

THEME_JS_TEMPLATE = """// Theme hooks placeholder for scaffold parity.
"""

GUIDANCE_JS_TEMPLATE = """// Guidance hooks placeholder for scaffold parity.
"""

PNG_PLACEHOLDER_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
)

TRANSLATIONS_EN_TEMPLATE = """home:
  sacred_text: "Sacred Text"
nav:
  home: "Home"
"""

TRANSLATIONS_HI_TEMPLATE = """home:
  sacred_text: "पवित्र ग्रंथ"
nav:
  home: "मुखपृष्ठ"
"""


def _default_collection_scene_entries(collection: str) -> dict:
    display_name = collection.replace('-', ' ').title()
    context = _infer_collection_scene_context(collection)
    return {
        "title-page": {
            "title": f"{display_name} Title Page",
            "description": (
                f"{display_name}: {context['title_focus']}.\n"
                f"Primary subject: {context['subject']} in a {context['setting']}.\n"
                f"Mood and lighting: {context['mood']} with soft divine glow.\n"
                f"Symbolic details: {context['imagery']}."
            ),
        },
        "card-page": {
            "title": f"{display_name} Card Image",
            "description": (
                f"Collection card for {display_name} centered on {context['subject']}.\n"
                f"Use a clean iconic composition with {context['imagery']} and {context['mood']}.\n"
                "Keep framing landscape-friendly for listing cards with clear text contrast."
            ),
        },
    }


def _infer_collection_scene_context(collection: str) -> dict:
    """Infer lightweight scene context from collection key for better default prompts."""
    tokens = set(collection.replace("_", "-").lower().split("-"))
    subject = "the central spiritual figure"
    setting = "sacred Indian visual environment"
    mood = "devotional, serene, and uplifting"
    imagery = "traditional symbols, temple textures, and sacred light motifs"
    title_focus = "Heroic devotional portrait composition"

    if "hanuman" in tokens:
        subject = "Lord Hanuman"
        setting = "Ramayana-inspired sacred setting with subtle Vanara-warrior cues"
        mood = "courageous bhakti, strength, and compassion"
        imagery = "gada (mace), saffron aura, and Ram-nam devotional motifs"
        title_focus = "Powerful Hanuman portrait with compassionate expression"
    elif "shiv" in tokens or "shiva" in tokens:
        subject = "Lord Shiva"
        setting = "Kailash-inspired cosmic mountain and meditative Shaiva ambience"
        mood = "tranquil, ascetic, and deeply contemplative"
        imagery = "trishul, damaru, crescent moon, rudraksha, and sacred ash motifs"
        title_focus = "Majestic Shiva portrait balancing stillness and power"
    elif "krishna" in tokens:
        subject = "Lord Krishna"
        setting = "Vrindavan-inspired devotional setting with natural elegance"
        mood = "playful divine love, grace, and wisdom"
        imagery = "flute, peacock feather, lotus, and gentle pastoral elements"
        title_focus = "Radiant Krishna portrait with divine charm"
    elif "ram" in tokens or "rama" in tokens:
        subject = "Lord Rama"
        setting = "Ayodhya or forest-epic devotional backdrop"
        mood = "dharma, nobility, and compassionate leadership"
        imagery = "bow-arrow, royal dharmic motifs, and warm golden light"
        title_focus = "Noble Rama portrait conveying dharma and compassion"
    elif "gita" in tokens or "bhagavad" in tokens:
        subject = "Lord Krishna and Arjuna"
        setting = "Kurukshetra-inspired sacred battlefield transformed into spiritual teaching space"
        mood = "clarity, guidance, and spiritual resolve"
        imagery = "chariot symbolism, dharma motifs, and luminous teaching aura"
        title_focus = "Krishna as divine teacher guiding Arjuna"
    elif "puran" in tokens or "puranam" in tokens or "bhagavat" in tokens:
        subject = "a revered deity with Rishi narration context"
        setting = "Puranic storytelling environment with temple and manuscript aesthetics"
        mood = "timeless wisdom, sacred storytelling, and devotion"
        imagery = "palm-leaf manuscript motifs, sages, and mythic sacred symbols"
        title_focus = "Mythic Puranic title portrait with narrative depth"

    return {
        "subject": subject,
        "setting": setting,
        "mood": mood,
        "imagery": imagery,
        "title_focus": title_focus,
    }


def upsert_collection_scene_entries(scenes_file: Path, collection: str) -> bool:
    """Ensure title-page and card-page scene entries exist in scene YAML."""
    defaults = _default_collection_scene_entries(collection)
    display_name = collection.replace('-', ' ').title()

    if scenes_file.exists():
        raw = scenes_file.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            data = {}
    else:
        data = {}

    meta = data.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("collection", collection)
    meta.setdefault("description", f"Scene descriptions for {display_name} image generation")
    data["_meta"] = meta

    scenes = data.get("scenes")
    if not isinstance(scenes, dict):
        scenes = {}

    changed = False
    for key, value in defaults.items():
        if key not in scenes or not isinstance(scenes[key], dict):
            scenes[key] = value
            changed = True
        else:
            if "title" not in scenes[key]:
                scenes[key]["title"] = value["title"]
                changed = True
            if "description" not in scenes[key]:
                scenes[key]["description"] = value["description"]
                changed = True

    data["scenes"] = scenes

    if not scenes_file.exists():
        changed = True

    if changed:
        scenes_file.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000),
            encoding="utf-8"
        )
    return changed


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
        "_data/translations/en.yml": TRANSLATIONS_EN_TEMPLATE,
        "_data/translations/hi.yml": TRANSLATIONS_HI_TEMPLATE,
        ".gitignore": GITIGNORE_CONTENT,
        "Gemfile": GEMFILE_CONTENT,
        "_config.yml": JEKYLL_CONFIG_TEMPLATE.format(project_name=project_name),
        "_layouts/default.html": DEFAULT_LAYOUT_TEMPLATE,
        "_layouts/home.html": HOME_LAYOUT_TEMPLATE,
        "_layouts/collection.html": COLLECTION_LAYOUT_TEMPLATE,
        "_layouts/verse.html": VERSE_LAYOUT_TEMPLATE,
        "assets/css/style.css": STYLE_CSS_TEMPLATE,
        "assets/css/print.css": PRINT_CSS_TEMPLATE,
        "assets/js/navigation.js": NAVIGATION_JS_TEMPLATE,
        "assets/js/language.js": LANGUAGE_JS_TEMPLATE,
        "assets/js/theme.js": THEME_JS_TEMPLATE,
        "assets/js/guidance.js": GUIDANCE_JS_TEMPLATE,
        "index.html": INDEX_HTML_TEMPLATE.replace("__PROJECT_NAME__", project_name),
        "README.md": README_TEMPLATE.format(project_name=project_name),
    }

    # Add example theme if not minimal
    if not minimal:
        files["data/themes/.gitkeep"] = "# Theme files go in subdirectories by collection\n# Example: data/themes/hanuman-chalisa/modern-minimalist.yml\n"

    for file_path, content in files.items():
        full_path = base_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
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


def create_theme_image_placeholders(base_path: Path, collection: str, theme: str = "modern-minimalist") -> None:
    """Create deterministic theme-scoped placeholder images for title/card pages."""
    images_dir = base_path / "images" / collection / theme
    images_dir.mkdir(parents=True, exist_ok=True)
    placeholder_bytes = base64.b64decode(PNG_PLACEHOLDER_BASE64)

    title_page = images_dir / "title-page.png"
    if not title_page.exists():
        title_page.write_bytes(placeholder_bytes)
        print(f"✓ Created images/{collection}/{theme}/title-page.png")

    card_page = images_dir / "card-page.png"
    if not card_page.exists():
        card_page.write_bytes(placeholder_bytes)
        print(f"✓ Created images/{collection}/{theme}/card-page.png")


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
    if upsert_collection_scene_entries(scenes_file, collection):
        print(f"✓ Created data/scenes/{collection}.yml")

    # Create canonical theme-scoped title/card placeholders so first-run UI is complete.
    create_theme_image_placeholders(base_path, collection)

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

    # Create collection landing page for local Jekyll preview.
    collection_page = base_path / collection / "index.html"
    collection_page.parent.mkdir(parents=True, exist_ok=True)
    if not collection_page.exists():
        display_name = collection.replace("-", " ").title()
        collection_page.write_text(
            COLLECTION_INDEX_TEMPLATE.format(display_name=display_name, collection_key=collection),
            encoding="utf-8"
        )
        print(f"✓ Created {collection}/index.html")

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
    print("      Collection title/card images are auto-generated when missing.")
    print(f"   6. Review/edit generated verses in _verses/{collection}/ for quality")
    print("   7. Preview locally and verify output:")
    print("      bundle install")
    print("      bundle exec jekyll serve")
    print("")
    print("   ✅ Core flow complete (steps 1-7).")
    print("   Optional next steps:")
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
