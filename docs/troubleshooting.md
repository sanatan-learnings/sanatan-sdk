# Troubleshooting

Common issues and solutions for sanatan-verse-sdk.

## Installation Issues

### "Command not found: verse-generate"

The installed commands are not in your PATH.

**Solution 1**: Add to PATH

```bash
export PATH="$HOME/Library/Python/3.13/bin:$PATH"  # macOS
export PATH="$HOME/.local/bin:$PATH"  # Linux
```

Add to your shell config (`~/.zshrc` or `~/.bashrc`) to make permanent.

**Solution 2**: Use full path

```bash
# Find the installation path
which verse-generate

# Then use the full path
/path/to/verse-generate --collection hanuman-chalisa --verse 5
```

**Solution 3**: Reinstall

```bash
pip install --user sanatan-verse-sdk
```

### "ModuleNotFoundError: No module named 'verse_sdk'"

SDK not installed or installed in wrong environment.

**Solution**:

```bash
pip install sanatan-verse-sdk
# Or for development:
pip install -e /path/to/sanatan-verse-sdk
```

## API Key Issues

### "Error: OPENAI_API_KEY not set"

OpenAI API key not configured.

**Solution 1**: Environment variable

```bash
export OPENAI_API_KEY=sk-your_key_here
```

**Solution 2**: .env file

```bash
echo "OPENAI_API_KEY=sk-your_key_here" >> .env
export $(cat .env | xargs)
```

**Verify**:

```bash
echo $OPENAI_API_KEY
```

### "Error: ELEVENLABS_API_KEY not set"

ElevenLabs API key not configured.

**Solution**:

```bash
export ELEVENLABS_API_KEY=your_key_here
# Or add to .env file
```

Get your key from: https://elevenlabs.io/app/settings/api-keys

### "Invalid API key"

API key is incorrect or expired.

**Check**:
- OpenAI: https://platform.openai.com/api-keys
- ElevenLabs: https://elevenlabs.io/app/settings/api-keys

**Solution**:
- Verify key is copied correctly (no extra spaces)
- Check key has not been revoked
- Ensure account has credits/quota

## Generation Issues

### "Error: Scene description not found"

Trying to generate image but scene description file doesn't exist in `data/scenes/<collection>.yml`.

**Solution**:

Create the scene description file:

```bash
# Create scene description file for your collection
touch data/scenes/hanuman-chalisa.yml

# Add scene descriptions for each verse in YAML format
# Then generate image
verse-generate --collection hanuman-chalisa --verse 5 --image
```

Or use verse-generate with a collection that already has scene descriptions.

### "Error: Verse file not found"

Trying to generate audio but verse markdown file doesn't exist.

**Solution**:

Create the verse file first, or ensure the verse exists in your collection:

```bash
# Check verse files exist
ls _verses/hanuman-chalisa/

# Then generate audio
verse-generate --collection hanuman-chalisa --verse 5 --audio
```

Or generate both image and audio at once (default behavior):

```bash
verse-generate --collection hanuman-chalisa --verse 5
```

### "Error: No devanagari field found"

Verse file exists but missing `devanagari:` field required for audio.

**Solution**:

Edit the verse file and add:

```yaml
---
devanagari: |
  Your Sanskrit text in Devanagari script
---
```

### "Error: Theme configuration not found"

Theme file missing or incorrectly named.

**Solution**:

Create theme configuration:

```bash
cat > data/themes/hanuman-chalisa/modern-minimalist.yml << EOF
name: modern-minimalist
style_modifier: |
  Your style description here...
size: 1024x1792
quality: standard
style: natural
EOF
```

### "Generation failed: Rate limit exceeded"

Hit OpenAI or ElevenLabs rate limits.

**Solution**:
- Wait a few minutes and retry
- For bulk operations, add delays between requests
- Check your API plan limits

## File Issues

### "Permission denied"

Cannot write to output directory.

**Solution**:

```bash
# Check permissions
ls -ld images/ audio/ data/

# Fix permissions
chmod 755 images/ audio/ data/

# Or create directories
mkdir -p images/modern-minimalist audio data
```

### "Directory not found"

Required directories don't exist.

**Solution**:

```bash
mkdir -p _verses data/themes images/modern-minimalist audio data
```

### Generated files are empty

Generation succeeded but files are empty or corrupt.

**Check**:
- API key is valid
- Network connection is stable
- API response wasn't an error

**Solution**:

```bash
# Delete empty file
rm images/modern-minimalist/chapter-01-verse-05.png

# Regenerate
verse-images --theme-name modern-minimalist --regenerate chapter-01-verse-05.png
```

## Model/Provider Issues

### "Model not found" (HuggingFace)

HuggingFace model not downloaded.

**Solution**:

```bash
# First run downloads the model (~80MB)
verse-embeddings --multi-collection --collections-file _data/collections.yml --provider huggingface
```

Wait for download to complete.

### "Out of memory" (HuggingFace)

Not enough RAM for local embeddings model.

**Solution**:

Use OpenAI provider instead:

```bash
verse-embeddings --multi-collection --collections-file _data/collections.yml --provider openai

### "ValidationException: expected maxLength: 2048" (Bedrock Cohere)

If Bedrock Cohere rejects long inputs, use a truncation policy:

```bash
verse-embeddings --provider bedrock-cohere --truncate-policy drop
```

Or explicitly set the limit:

```bash
verse-embeddings --provider bedrock-cohere --max-input-chars 2048 --truncate-policy truncate
```
```

Requires API key but no local processing.

## Network Issues

### "Connection timeout"

Network request to API failed.

**Check**:
- Internet connection
- Firewall/proxy settings
- API service status (status.openai.com, status.elevenlabs.io)

**Solution**:
- Retry the command
- Check your network connection
- Use VPN if behind restrictive network

### "SSL certificate error"

Certificate verification failed.

**Solution**:

```bash
# Update certificates (macOS)
pip install --upgrade certifi

# Or update Python SSL
brew reinstall openssl
```

## Common Mistakes

### Running commands from wrong directory

Commands expect project structure to exist.

**Solution**:

```bash
cd /path/to/your/project  # Project root with _verses/, docs/, etc.
verse-generate --collection hanuman-chalisa --verse 5
```

### Missing .env file

Environment variables not loaded.

**Solution**:

```bash
# Create .env file
cat > .env << EOF
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
EOF

# Load variables
export $(cat .env | xargs)
```

### Using wrong command syntax

Old or incorrect command syntax.

**Check**:

```bash
verse-generate --help
verse-images --help
verse-audio --help
verse-embeddings --help
```

## Getting Help

If issue persists:

1. **Check logs**: Look for detailed error messages
2. **Verify setup**:
   ```bash
   # Check installation
   pip show sanatan-verse-sdk

   # Check commands
   which verse-generate

   # Check API keys
   echo $OPENAI_API_KEY | cut -c1-10
   ```

3. **GitHub Issues**: https://github.com/sanatan-learnings/sanatan-verse-sdk/issues

4. **Include in issue**:
   - Error message (full output)
   - Command you ran
   - Python version: `python --version`
   - OS version
   - sanatan-verse-sdk version: `pip show sanatan-verse-sdk`

## See Also

- [verse-generate](commands/verse-generate.md) - Main generation command
- [verse-images](commands/verse-images.md) - Image generation
- [verse-audio](commands/verse-audio.md) - Audio generation
- [verse-embeddings](commands/verse-embeddings.md) - Embeddings generation
