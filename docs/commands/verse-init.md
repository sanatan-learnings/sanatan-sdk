# verse-init

Initialize a new verse project with recommended directory structure and template files.

## Synopsis

```bash
verse-init [OPTIONS]
```

## Description

The `verse-init` command scaffolds a new verse collection project with the recommended directory structure, template configuration files, and optional example collections. This is the fastest way to get started with sanatan-verse-sdk.

## Options

### Optional

- `--project-name NAME` - Create project in new subdirectory with given name
- `--collection NAME` - Create collection with template files (can be used multiple times)
- `--num-verses N` - Number of canonical placeholder verse IDs per collection (default: 3)
- `--minimal` - Create minimal structure without example files

## Examples

### Initialize in Current Directory

```bash
# Initialize with full structure
verse-init

# Initialize with minimal structure
verse-init --minimal
```

This creates the structure in the current directory. You'll be prompted for confirmation if the directory is not empty.

### Create New Project Directory

```bash
# Create new project
verse-init --project-name my-verse-project

# Create with collection
verse-init --project-name hanuman-gpt --collection hanuman-chalisa
```

This creates a new subdirectory with the project name and initializes the structure inside it.

### Add Collections to Existing Project

**Important**: You can run `verse-init --collection` in an existing project to add new collections!

```bash
# In your existing project directory
cd my-existing-project

# Add a new collection
verse-init --collection sundar-kaand --num-verses 60

# Or add multiple collections
verse-init --collection sundar-kaand --collection bhagavad-gita
```

**What happens:**
- ✅ Creates new collection files (doesn't overwrite existing)
- ✅ Appends to `_data/collections.yml` (preserves existing collections)
- ✅ Creates templates for the new collection only

**Safety**: Existing files are never overwritten.

### Initialize with Collections

```bash
# Single collection with 3 canonical placeholders (default)
verse-init --collection hanuman-chalisa

# Single collection with custom number of verses
verse-init --collection sundar-kaand --num-verses 10

# Multiple collections
verse-init --collection hanuman-chalisa --collection sundar-kaand

# Complete setup
verse-init --project-name my-project \
  --collection hanuman-chalisa --num-verses 43 \
  --collection sundar-kaand --num-verses 60
```

**What gets created for each collection:**
- ✅ Canonical text template: `data/verses/<collection>.yaml`
- ✅ Source text placeholder: `data/sources/<collection>.txt`
- ✅ Sample theme: `data/themes/<collection>/modern-minimalist.yml`
- ✅ Scene descriptions template (includes `title-page`): `data/scenes/<collection>.yml`
- ✅ Card image placeholder: `images/<collection>/card.svg`
- ✅ Title image placeholder: `images/<collection>/title.svg`
- ✅ Collection landing page: `<collection>/index.md`
- ✅ Collection entry in `_data/collections.yml`

## Created Structure

The command creates the following directory structure:

```
your-project/
├── .env.example                 # API keys template
├── .gitignore                   # Git ignore file
├── README.md                    # Project documentation
├── _data/
│   └── collections.yml          # Collection registry
├── _verses/                     # Verse markdown files
├── data/
│   ├── themes/                  # Theme configurations
│   ├── verses/                  # Canonical verse YAML files
│   ├── scenes/                  # Scene descriptions
│   └── sources/                 # Canonical plain-text source files
├── images/                      # Generated images (gitignored)
└── audio/                       # Generated audio (gitignored)
```

## Template Files

### .env.example

Contains placeholders for required API keys:
- `OPENAI_API_KEY` - For images, embeddings, content generation
- `ELEVENLABS_API_KEY` - For audio generation

### _data/collections.yml

Template for defining collections with example structure.

### .gitignore

Configured to ignore:
- Generated content (images, audio, embeddings)
- Environment files (.env)
- Python cache files

### README.md

Project documentation with:
- Setup instructions
- Directory structure explanation
- Links to SDK documentation

## Workflow

For the full lifecycle (init → generate → embeddings → index → deploy), see `docs/end-to-end-workflow.md`.

### New Project with Collection

```bash
# 1. Initialize with collection
verse-init --project-name my-verse-project --collection hanuman-chalisa
cd my-verse-project

# 2. Configure API keys
cp .env.example .env
# Edit .env and add your actual API keys

# 3. Add canonical text
# Edit data/verses/hanuman-chalisa.yaml

# 4. Validate
verse-validate

# 5. Generate
verse-generate --collection hanuman-chalisa --verse 1
```

### Add Collection to Existing Project

```bash
# 1. Navigate to existing project
cd my-existing-project

# 2. Add new collection
verse-init --collection sundar-kaand --num-verses 60

# 3. Add canonical text
# Edit data/verses/sundar-kaand.yaml

# 4. Validate
verse-validate

# 5. Generate
verse-generate --collection sundar-kaand --verse 1
```

## After Initialization

Once initialized, you should:

1. **Set up API keys**
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys
   ```

2. **Define collections**
   Edit `_data/collections.yml` to add your collections:
   ```yaml
   hanuman-chalisa:
     enabled: true
     name:
       en: "Hanuman Chalisa"
       hi: "हनुमान चालीसा"
     subdirectory: "hanuman-chalisa"
     permalink_base: "/hanuman-chalisa"
     total_verses: 43
   ```

3. **Add canonical verse text**
   Create `data/verses/<collection>.yaml` with Devanagari text

4. **Validate structure**
   ```bash
   verse-validate
   ```

5. **Generate content**
   ```bash
   verse-generate --collection <collection-key> --verse 1
   ```

## Notes

- **Safe for existing projects**: Can add collections to existing projects without overwriting files
- **Prompts for confirmation**: When run in non-empty directory
- **Never overwrites**: Existing files are preserved, only new files are created
- **Appends to collections.yml**: New collections are added to existing registry
- **Creates `.gitignore`**: Configured to prevent committing generated content
- **Template files**: Use current best practices and conventions
- **Multiple uses**: Can be run multiple times to add more collections

## See Also

- [verse-validate](verse-validate.md) - Validate project structure
- [verse-generate](verse-generate.md) - Generate content
- [Usage Guide](../usage.md) - Complete setup guide
