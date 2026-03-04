# verse-add

Add new verse placeholders to existing collections.

## Synopsis

```bash
verse-add --collection COLLECTION --verse NUMBER [OPTIONS]
```

## Description

The `verse-add` command adds new verse entries to an existing collection. By default, it **only updates the canonical YAML file** (`data/verses/<collection>.yaml`) with placeholder entries. Markdown files are auto-created by `verse-generate` when needed.

**Smart Format Detection**: The command automatically infers the verse naming format from existing entries:
- If you have `verse-01`, `verse-02`, it will continue with `verse-03`
- If you have `chaupai-1`, `chaupai-2`, it will use that format
- If you have `chapter-01-shloka-01`, it will continue with the chapter-based format

**Chapter Support (v0.26.0+)**: For multi-chapter collections like the Bhagavad Gita, use the `--chapter` flag to specify which chapter to add verses to.

This is useful when:
- Expanding a collection with additional verses
- Adding missing verses to an incomplete collection
- Batch-creating verse placeholders for new content
- Adding verses to specific chapters in multi-chapter texts

## Options

### Required

- `--collection COLLECTION` - Collection key (e.g., `hanuman-chalisa`)
- `--verse NUMBER` - Verse number or range (e.g., `44` or `44-50`)

### Optional

- `--chapter NUMBER` - Chapter number for chapter-based formats (e.g., `--chapter 2`)
- `--markdown` - Create markdown files (not recommended - auto-created by verse-generate)
- `--format FORMAT` - Verse ID format (default: auto-inferred)

## Examples

### Simple Collections

#### Add Single Verse (YAML Only)

```bash
verse-add --collection hanuman-chalisa --verse 44

# Output:
# 📝 Adding verses to Hanuman Chalisa
#    Collection: hanuman-chalisa
#    Verses: 44 (1 verse(s))
#
# Updating canonical YAML file:
#   ✓ Will add verse-44 to hanuman-chalisa.yaml
#   Format: verse-{:02d}
#
# Skipping markdown files (verse-generate will create them automatically)
#
# ✅ Summary:
#    YAML entries added: 1
```

This adds a placeholder entry to `data/verses/hanuman-chalisa.yaml` with `devanagari: ''`.

#### Add Multiple Verses (Range)

```bash
verse-add --collection hanuman-chalisa --verse 44-50

# Output:
# 📝 Adding verses to Hanuman Chalisa
#    Collection: hanuman-chalisa
#    Verses: 44-50 (7 verse(s))
#
# Updating canonical YAML file:
#   ✓ Will add verse-44 to hanuman-chalisa.yaml
#   ✓ Will add verse-45 to hanuman-chalisa.yaml
#   ...
#   ✓ Will add verse-50 to hanuman-chalisa.yaml
```

Adds 7 verses in one command (verses 44 through 50).

#### Add With Markdown Files (Optional)

```bash
verse-add --collection hanuman-chalisa --verse 44-50 --markdown

# Creates both YAML entries AND markdown files
# Usually not needed - verse-generate will create markdown automatically
```

### Chapter-Based Collections (NEW in v0.26.0)

#### Add Verses to Specific Chapter

```bash
verse-add --collection bhagavad-gita --verse 1-72 --chapter 2

# Output:
# 📝 Adding verses to Bhagavad Gita
#    Collection: bhagavad-gita
#    Verses: 1-72 (72 verse(s))
#    Chapter: 2
#
# Updating canonical YAML file:
#   📖 Using chapter 2 (detected format: chapter-{:02d})
#   ✓ Will add chapter-02-shloka-01 to bhagavad-gita.yaml
#   ✓ Will add chapter-02-shloka-02 to bhagavad-gita.yaml
#   ...
#   ✓ Will add chapter-02-shloka-72 to bhagavad-gita.yaml
```

#### Add Famous Verses

```bash
# Add the famous Karma Yoga verse (Chapter 2, Verse 47)
verse-add --collection bhagavad-gita --verse 47 --chapter 2

# Creates: chapter-02-shloka-47
```

#### Add Multiple Chapters

```bash
# Add all of Chapter 1 (47 shlokas)
verse-add --collection bhagavad-gita --verse 1-47 --chapter 1

# Add all of Chapter 2 (72 shlokas)
verse-add --collection bhagavad-gita --verse 1-72 --chapter 2

# Add all of Chapter 3 (43 shlokas)
verse-add --collection bhagavad-gita --verse 1-43 --chapter 3
```

## Output Files

### YAML Entry (Default - YAML Only)

`data/verses/<collection>.yaml`:

```yaml
verse-44:
  devanagari: ''
```

The entry is created with an empty string for the `devanagari` field. You should edit this file to add the actual Sanskrit/Devanagari text.

**Chapter-based format:**
```yaml
chapter-02-shloka-47:
  devanagari: ''
```

### Markdown File (Optional - with `--markdown` flag)

`_verses/<collection>/verse-44.md`:

```markdown
---
layout: verse
collection: hanuman-chalisa
verse_number: 44
title: "Verse 44"
---

Add verse content here.
```

**Note**: Markdown files are usually not created by `verse-add`. Instead, `verse-generate` auto-creates them when generating content, pulling the `devanagari` text from the YAML file.

## Workflow

### Simple Collections

```bash
# 1. Add verse placeholders (YAML only)
verse-add --collection hanuman-chalisa --verse 44-50

# 2. Edit canonical YAML file
# Edit data/verses/hanuman-chalisa.yaml
# Add Devanagari text for each new verse:
#   verse-44:
#     devanagari: 'तुलसी दास सदा हरि चेरा। कीजै नाथ हृदय महँ डेरा।।'

# 3. Generate content (auto-creates markdown + multimedia)
verse-generate --collection hanuman-chalisa --verse 44
# This auto-creates _verses/hanuman-chalisa/verse-44.md
# Plus images, audio, and embeddings
```

### Chapter-Based Collections

```bash
# 1. Add verses to specific chapter
verse-add --collection bhagavad-gita --verse 1-72 --chapter 2

# 2. Edit canonical YAML file
# Edit data/verses/bhagavad-gita.yaml
# Add Devanagari text:
#   chapter-02-shloka-47:
#     devanagari: 'कर्मण्येवाधिकारस्ते मा फलेषु कदाचन...'

# 3. Generate content for specific verse
verse-generate --collection bhagavad-gita --verse chapter-02-shloka-47
```

## Behavior

### Existing Verses

If a verse already exists, it will be skipped:

```bash
verse-add --collection hanuman-chalisa --verse 1

# Output:
# ⚠️  Skipped verse-01 (already exists)
```

Safe to run multiple times - won't overwrite existing content.

### File Creation

- **YAML file**: Created if it doesn't exist, updated if it does
- **Markdown files**: Only created if they don't exist
- **Directories**: Created automatically if needed (`data/verses/`, `_verses/<collection>/`)

## Use Cases

### Expanding a Simple Collection

```bash
# Collection has verses 1-43, add verse 44
verse-add --collection hanuman-chalisa --verse 44
```

### Adding Missing Verses

```bash
# Collection is missing verses 10-15
verse-add --collection sundar-kaand --verse 10-15
```

### Multi-Chapter Collections

```bash
# Create placeholders for all Bhagavad Gita Chapter 1 verses
verse-add --collection bhagavad-gita --verse 1-47 --chapter 1

# Add Chapter 2 (Karma Yoga - 72 verses)
verse-add --collection bhagavad-gita --verse 1-72 --chapter 2

# Add specific verses from Chapter 18
verse-add --collection bhagavad-gita --verse 65-66 --chapter 18
```

### Batch Creation Across Chapters

```bash
# Add all 18 chapters of Bhagavad Gita
for chapter in {1..18}; do
  case $chapter in
    1) verses=47 ;;
    2) verses=72 ;;
    3) verses=43 ;;
    4) verses=42 ;;
    # ... etc
  esac
  verse-add --collection bhagavad-gita --verse 1-$verses --chapter $chapter
done
```

## Next Steps After Adding

1. **Edit canonical YAML** - Add Devanagari text in `data/verses/<collection>.yaml`:
   ```yaml
   chapter-02-shloka-47:
     devanagari: 'कर्मण्येवाधिकारस्ते मा फलेषु कदाचन...'
   ```

2. **Collection metadata auto-sync** - `verse-add` automatically updates `total_verses` in `_data/collections.yml`

3. **Generate content** - Run `verse-generate` to create markdown, images, audio, and embeddings:
   ```bash
   verse-generate --collection bhagavad-gita --verse chapter-02-shloka-47
   ```

4. **Validate** - Run `verse-validate` to ensure everything is correct

## Integration with Other Commands

- **verse-validate** - Validates project structure and YAML format
- **verse-generate** - Generates multimedia for newly added verses (auto-creates markdown)
- **verse-status** - Check which verses have complete content
- **verse-init** - Creates initial structure (use verse-add for expansion)

## Error Handling

```bash
# Collection doesn't exist
verse-add --collection unknown --verse 1
# Error: Collection 'unknown' not found in collections.yml

# Invalid verse format
verse-add --collection hanuman-chalisa --verse abc
# Error: Invalid verse format 'abc'. Use a number or range

# Missing required arguments
verse-add --collection hanuman-chalisa
# Error: the following arguments are required: --verse
```

## Tips

1. **Use Ranges**: Add multiple verses efficiently with ranges (`1-72` instead of adding one at a time)

2. **YAML First**: The default YAML-only mode is recommended - let `verse-generate` auto-create markdown files

3. **Chapter-Based Collections**: Use `--chapter` flag for organized multi-chapter content:
   ```bash
   verse-add --collection bhagavad-gita --verse 1-72 --chapter 2
   ```

4. **Validate After Adding**: Run `verse-validate` to check project structure

5. **Metadata is auto-synced**: `total_verses` in `_data/collections.yml` is updated automatically

6. **Consistent Format**: The SDK auto-detects format, but ensure your first verses use the format you want:
   - `verse-01` for simple collections
   - `chapter-01-shloka-01` for chapter-based collections

7. **Version Control**: Always commit canonical YAML files to version control

8. **Fill in Text Immediately**: After adding verses, edit the YAML file right away to add Devanagari text while it's fresh

## See Also

- [verse-init](verse-init.md) - Initialize new projects
- [verse-validate](verse-validate.md) - Validate project structure
- [verse-generate](verse-generate.md) - Generate multimedia content (auto-creates markdown)
- [verse-status](verse-status.md) - Check completion status
- [Chapter-Based Formats Guide](../chapter-based-formats.md) - Detailed guide for multi-chapter collections
- [Local Verses Guide](../local-verses.md) - YAML file format and structure
