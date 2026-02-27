# Development Guide

This guide is for developers who want to contribute to sanatan-verse-sdk or understand its internal structure.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Debugging](#debugging)
- [Working with Components](#working-with-components)

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- Virtual environment tool (venv, virtualenv, or conda)
- OpenAI API key (for testing)
- ElevenLabs API key (for testing)

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/sanatan-learnings/sanatan-verse-sdk.git
cd sanatan-verse-sdk

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .
```

### Environment Configuration

Copy the example environment file and add your API keys:

```bash
# In your project root (not in sanatan-verse-sdk)
cp /path/to/sanatan-verse-sdk/.env.example .env

# Edit .env and add your actual API keys
# Get keys from:
# - OpenAI: https://platform.openai.com/api-keys
# - ElevenLabs: https://elevenlabs.io/app/settings/api-keys
```

### Verify Installation

```bash
# Check all commands are available
verse-generate --help
verse-translate --help
verse-status --help
verse-sync --help
verse-images --help
verse-audio --help
verse-embeddings --help
verse-deploy --help
```

## Project Structure

```
sanatan-verse-sdk/
├── verse_sdk/                   # Main package
│   ├── __init__.py
│   ├── audio/                   # Audio generation module
│   │   ├── __init__.py
│   │   └── generate_audio.py   # ElevenLabs integration
│   ├── cli/                     # Command-line interface
│   │   ├── __init__.py
│   │   └── generate.py          # Main orchestrator command
│   ├── deployment/              # Deployment utilities
│   │   ├── __init__.py
│   │   └── deploy.py            # Cloudflare Worker deployment
│   ├── embeddings/              # Vector embeddings
│   │   ├── __init__.py
│   │   ├── generate_embeddings.py      # Multi-collection embeddings
│   │   ├── generate_embeddings_local.py # Local embeddings
│   │   └── local_embeddings.py          # Embedding utilities
│   ├── fetch/                   # Text fetching
│   │   ├── __init__.py
│   │   └── fetch_verse_text.py  # Scrape authoritative sources
│   ├── images/                  # Image generation
│   │   ├── __init__.py
│   │   └── generate_theme_images.py # DALL-E 3 integration
│   └── utils/                   # Shared utilities
│       ├── __init__.py
│       ├── file_utils.py        # File operations
│       └── yaml_parser.py       # YAML parsing
├── docs/                        # Documentation
│   ├── commands/                # Command-specific docs
│   ├── development.md           # This file
│   ├── multi-collection.md      # Multi-collection guide
│   ├── publishing.md            # Publishing to PyPI
│   └── troubleshooting.md       # Common issues
├── examples/                    # Example configurations
├── scripts/                     # Development scripts
│   ├── publish.sh               # PyPI publishing
│   └── test_multi_collection.py # Multi-collection testing
├── setup.py                     # Package configuration
├── requirements.txt             # Dependencies
├── CONTRIBUTING.md              # Contribution guidelines
└── README.md                    # Main documentation
```

## Development Workflow

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Edit code in `verse_sdk/` directory
   - Follow existing code patterns
   - Add docstrings to new functions

3. **Test locally**
   ```bash
   # Test the command you modified
   verse-generate --collection hanuman-chalisa --verse 1 --help
   ```

4. **Commit and push**
   ```bash
   git add .
   git commit -m "Add feature: description"
   git push origin feature/your-feature-name
   ```

### Code Style

- Follow PEP 8 conventions
- Use meaningful variable names
- Add type hints for function parameters
- Include docstrings for public functions
- Keep functions focused and single-purpose

Example:
```python
def generate_audio(collection: str, verse_id: str, speed: str = "full") -> bool:
    """
    Generate audio pronunciation for a verse.

    Args:
        collection: Collection key (e.g., 'hanuman-chalisa')
        verse_id: Verse identifier (e.g., 'verse_01')
        speed: Audio speed - 'full' or 'slow'

    Returns:
        True if successful, False otherwise
    """
    # Implementation
    pass
```

## Testing

### Manual Testing

Create a test project structure:

```bash
# Create test project
mkdir -p ~/test-verse-project
cd ~/test-verse-project

# Set up basic structure
mkdir -p _data _verses/hanuman-chalisa data/scenes data/themes/hanuman-chalisa

# Create collections.yml
cat > _data/collections.yml << EOF
hanuman-chalisa:
  enabled: true
  name:
    en: "Hanuman Chalisa"
    hi: "हनुमान चालीसा"
EOF

# Test commands
verse-generate --list-collections
verse-generate --collection hanuman-chalisa --verse 1
```

### Test Scripts

Run the multi-collection test:
```bash
cd sanatan-verse-sdk
python scripts/test_multi_collection.py
```

### Testing Individual Components

**Test image generation:**
```bash
verse-images --collection hanuman-chalisa --verse verse_01 --theme modern-minimalist
```

**Test audio generation:**
```bash
verse-audio --collection hanuman-chalisa --verse verse_01
```

**Test embeddings:**
```bash
verse-embeddings --multi-collection --collections-file _data/collections.yml
```

## Debugging

### Enable Verbose Output

Most commands support verbose output. Check the implementation and add print statements:

```python
print(f"DEBUG: Processing verse {verse_id} from {collection}")
```

### Common Issues

**Import Errors:**
```bash
# Reinstall in editable mode
pip install -e .
```

**API Key Issues:**
```bash
# Verify environment variables
echo $OPENAI_API_KEY
echo $ELEVENLABS_API_KEY

# Load from .env in your test project
cd ~/test-verse-project
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('OPENAI_API_KEY'))"
```

**Path Issues:**
```bash
# Check current directory structure
ls -la _data/
ls -la _verses/

# Verify collections.yml
cat _data/collections.yml
```

### Using Python Debugger

Add breakpoints in code:
```python
import pdb; pdb.set_trace()
```

Or use your IDE's debugger with the entry points in `setup.py`.

## Working with Components

### Adding a New Command

1. Create module in appropriate directory (e.g., `verse_sdk/newfeature/`)
2. Implement `main()` function
3. Add entry point in `setup.py`:
   ```python
   entry_points={
       'console_scripts': [
           'verse-newcommand=verse_sdk.newfeature.module:main',
       ],
   }
   ```
4. Reinstall: `pip install -e .`
5. Add documentation in `docs/commands/verse-newcommand.md`

### Adding Collection Support

To add support for a new verse collection:

1. **Add source in fetch module** (`verse_sdk/fetch/fetch_verse_text.py`):
   ```python
   SOURCES = {
       "new-collection": {
           "name": "New Collection",
           "url_template": "https://example.com/verse-{verse_num}",
           "selectors": [".verse-text", ".devanagari"]
       }
   }
   ```

2. **Update documentation** with collection-specific details

3. **Test with real data** from authoritative sources

### Modifying Image Generation

The image generation uses DALL-E 3. Key files:
- `verse_sdk/images/generate_theme_images.py` - Main logic
- Theme files in user project: `data/themes/{collection}/{theme}.yml`
- Scene descriptions in user project: `data/scenes/{collection}.yml`

### Modifying Audio Generation

The audio generation uses ElevenLabs. Key files:
- `verse_sdk/audio/generate_audio.py` - Main logic
- Generates both full-speed and slow-speed audio
- Output: `audio/{collection}/{verse_id}_{speed}.mp3`

### Modifying Embeddings

Vector embeddings for semantic search. Key files:
- `verse_sdk/embeddings/generate_embeddings.py` - Multi-collection support
- `verse_sdk/embeddings/local_embeddings.py` - Local embeddings (no API)
- Uses OpenAI's text-embedding-3-small model
- Output: `data/embeddings/collections/{collection}.json` + `data/embeddings/collections/index.json`

## Building and Publishing

See [Publishing Guide](publishing.md) for details on releasing new versions to PyPI.

## Additional Resources

- [Contributing Guide](../CONTRIBUTING.md) - Contribution guidelines
- [Command Reference](README.md) - All command documentation
- [Multi-Collection Guide](multi-collection.md) - Working with multiple collections
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

## Getting Help

- Check existing documentation first
- Review closed issues on GitHub
- Open a new issue with detailed information:
  - Python version
  - Operating system
  - Steps to reproduce
  - Error messages
  - Expected vs actual behavior
