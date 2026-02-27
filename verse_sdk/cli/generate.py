#!/usr/bin/env python3
"""
Collection-aware verse content generator - complete orchestration of all verse content.

This command is the one-stop solution for generating all content for a verse:
- Fetch traditional Devanagari text from canonical sources (optional)
- Regenerate AI content from canonical text (transliteration, meaning, translation, story)
- Generate AI image with DALL-E 3
- Generate audio pronunciation with ElevenLabs (full + slow speed)
- Update vector embeddings for semantic search

Usage:
    # Generate everything for a verse (default: image + audio, no embeddings)
    verse-generate --collection hanuman-chalisa --verse 15

    # Regenerate AI content only (no multimedia)
    verse-generate --collection sundar-kaand --verse 3 --regenerate-content

    # Regenerate content + image
    verse-generate --collection sundar-kaand --verse 3 --regenerate-content --image

    # Regenerate content + image + audio
    verse-generate --collection sundar-kaand --verse 3 --regenerate-content --image --audio

    # Generate only image
    verse-generate --collection sundar-kaand --verse 3 --image

    # Generate only audio
    verse-generate --collection sundar-kaand --verse 5 --audio

    # Generate image + embeddings (no audio)
    verse-generate --collection sundar-kaand --verse 5 --image --embeddings

Requirements:
    - OPENAI_API_KEY environment variable (for content generation, image generation, and embeddings)
    - ELEVENLABS_API_KEY environment variable (for audio generation)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    print("Error: python-dotenv package not installed")
    print("Install with: pip install python-dotenv")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed")
    print("Install with: pip install openai")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    # PIL is optional - only needed for image verification
    Image = None

# Load environment variables
load_dotenv()

# Global flag for debug mode
DEBUG_MODE = False


# ==================== Custom Exception Classes ====================

class UserFriendlyError(Exception):
    """Custom exception with user-friendly error messages and fix instructions."""

    def __init__(self, message: str, fix_instructions: List[str] = None):
        self.message = message
        self.fix_instructions = fix_instructions or []
        super().__init__(self.message)

    def display(self):
        """Display the error with formatting."""
        print(f"\n✗ Error: {self.message}\n", file=sys.stderr)
        if self.fix_instructions:
            print("How to fix:", file=sys.stderr)
            for i, instruction in enumerate(self.fix_instructions, 1):
                print(f"  {i}. {instruction}", file=sys.stderr)
            print()


# ==================== Cost Tracking ====================

class CostTracker:
    """Track API costs throughout generation."""

    # Pricing (as of 2024)
    GPT4_INPUT_COST = 0.03 / 1000  # $0.03 per 1K tokens
    GPT4_OUTPUT_COST = 0.06 / 1000  # $0.06 per 1K tokens
    DALLE3_STANDARD_COST = 0.040  # $0.040 per image (1024x1024)
    DALLE3_HD_COST = 0.080  # $0.080 per image (1024x1024 HD)
    ELEVENLABS_COST = 0.30 / 1000  # ~$0.30 per 1K characters
    EMBEDDING_COST = 0.0001 / 1000  # $0.0001 per 1K tokens

    def __init__(self):
        self.costs = {
            'content_generation': 0.0,
            'scene_generation': 0.0,
            'image_generation': 0.0,
            'audio_generation': 0.0,
            'embeddings': 0.0
        }

    def track_gpt4(self, category: str, input_tokens: int, output_tokens: int):
        """Track GPT-4 API cost."""
        cost = (input_tokens * self.GPT4_INPUT_COST) + (output_tokens * self.GPT4_OUTPUT_COST)
        self.costs[category] += cost
        return cost

    def track_dalle3(self, hd: bool = False):
        """Track DALL-E 3 image cost."""
        cost = self.DALLE3_HD_COST if hd else self.DALLE3_STANDARD_COST
        self.costs['image_generation'] += cost
        return cost

    def track_elevenlabs(self, character_count: int):
        """Track ElevenLabs audio cost."""
        cost = character_count * self.ELEVENLABS_COST
        self.costs['audio_generation'] += cost
        return cost

    def track_embeddings(self, token_count: int):
        """Track embedding generation cost."""
        cost = token_count * self.EMBEDDING_COST
        self.costs['embeddings'] += cost
        return cost

    def get_total(self) -> float:
        """Get total cost across all categories."""
        return sum(self.costs.values())

    def format_cost(self, cost: float) -> str:
        """Format cost for display."""
        if cost < 0.01:
            return f"${cost:.4f}"
        return f"${cost:.2f}"


# ==================== File Verification ====================

def verify_image_file(image_path: Path) -> Tuple[bool, str, int]:
    """
    Verify that an image file exists and is valid.

    Returns:
        (is_valid, message, file_size)
    """
    if not image_path.exists():
        return False, "File not found", 0

    file_size = image_path.stat().st_size

    if file_size == 0:
        return False, "File is empty", 0

    if file_size < 1000:  # Less than 1KB is suspicious
        return False, f"File is too small ({file_size} bytes)", file_size

    # Try to open with PIL if available
    if Image:
        try:
            with Image.open(image_path) as img:
                # Verify it can be loaded
                img.verify()
            return True, "Valid image", file_size
        except Exception as e:
            return False, f"Invalid image format: {str(e)}", file_size
    else:
        # Without PIL, just check extension and size
        if image_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
            return True, "Image exists (format not verified)", file_size
        return False, "Unknown image format", file_size


def verify_audio_files(collection: str, verse_id: str) -> Tuple[bool, str, List[Tuple[Path, int]]]:
    """
    Verify that audio files exist and are valid.

    Returns:
        (is_valid, message, [(file_path, file_size), ...])
    """
    audio_dir = Path.cwd() / "public" / "audio" / collection
    audio_files = []

    # Check for both normal and slow versions
    normal_file = audio_dir / f"{verse_id}-full.mp3"
    slow_file = audio_dir / f"{verse_id}-slow.mp3"

    all_valid = True
    messages = []

    for audio_file, label in [(normal_file, "normal"), (slow_file, "slow")]:
        if not audio_file.exists():
            all_valid = False
            messages.append(f"{label} version not found")
            continue

        file_size = audio_file.stat().st_size

        if file_size == 0:
            all_valid = False
            messages.append(f"{label} version is empty")
        elif file_size < 1000:  # Less than 1KB is suspicious
            all_valid = False
            messages.append(f"{label} version too small ({file_size} bytes)")
        else:
            audio_files.append((audio_file, file_size))

    if all_valid:
        return True, "All audio files valid", audio_files
    else:
        return False, "; ".join(messages), audio_files


def verify_verse_file(verse_file: Path) -> Tuple[bool, str, int]:
    """
    Verify that a verse markdown file exists and has required frontmatter.

    Returns:
        (is_valid, message, file_size)
    """
    if not verse_file.exists():
        return False, "File not found", 0

    file_size = verse_file.stat().st_size

    if file_size == 0:
        return False, "File is empty", 0

    try:
        with open(verse_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for frontmatter
        if not content.startswith('---'):
            return False, "Missing frontmatter", file_size

        parts = content.split('---', 2)
        if len(parts) < 3:
            return False, "Invalid frontmatter format", file_size

        # Parse frontmatter
        frontmatter = yaml.safe_load(parts[1])

        # Check required fields
        required_fields = ['verse_id', 'devanagari']
        missing_fields = [f for f in required_fields if f not in frontmatter]

        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}", file_size

        return True, "Valid verse file", file_size

    except Exception as e:
        return False, f"Error reading file: {str(e)}", file_size


def format_file_size(size_bytes: int) -> str:
    """Format file size for display."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# ==================== Progress Indicators ====================

class ProgressBar:
    """Simple ASCII progress bar for tracking long operations."""

    def __init__(self, total: int, width: int = 10, filled_char: str = "●", empty_char: str = "○"):
        self.total = total
        self.current = 0
        self.width = width
        self.filled_char = filled_char
        self.empty_char = empty_char

    def update(self, current: int, message: str = ""):
        """Update progress bar to current position."""
        self.current = current
        self.display(message)

    def display(self, message: str = ""):
        """Display the progress bar."""
        if self.total == 0:
            percentage = 100
            filled = self.width
        else:
            percentage = int((self.current / self.total) * 100)
            filled = int((self.current / self.total) * self.width)

        empty = self.width - filled
        bar = self.filled_char * filled + self.empty_char * empty

        # Build progress line
        progress_line = f"[{bar}] {percentage:3d}%"
        if message:
            progress_line += f" - {message}"

        # Print with carriage return to overwrite previous line
        print(f"\r{progress_line}", end="", flush=True)

    def finish(self, message: str = ""):
        """Complete the progress bar and move to next line."""
        self.current = self.total
        self.display(message)
        print()  # Move to next line

    def increment(self, message: str = ""):
        """Increment progress by 1."""
        self.update(self.current + 1, message)


def extract_verse_marker(text: str) -> Optional[str]:
    """
    Extract Devanagari verse marker from text (e.g., ॥ १-१॥ or ॥१-१॥).

    Args:
        text: Text containing potential verse marker

    Returns:
        Devanagari verse marker if found, None otherwise
    """
    import re
    # Match Devanagari verse markers: ॥ digits-digits ॥ or ॥digits-digits॥
    # Also handles single verse numbers: ॥ १ ॥ or ॥१॥
    pattern = r'॥\s*[०-९०-९\d]+(?:-[०-९\d]+)?\s*॥'
    match = re.search(pattern, text)
    return match.group(0) if match else None


def normalize_transliteration_markers(transliteration: str, devanagari_text: str) -> str:
    """
    Ensure transliteration has consistent Devanagari verse markers.

    Removes ASCII markers and ensures Devanagari markers from source are preserved.

    Args:
        transliteration: AI-generated transliteration
        devanagari_text: Source Devanagari text with markers

    Returns:
        Transliteration with consistent Devanagari markers
    """
    import re

    # Extract Devanagari marker from source
    devanagari_marker = extract_verse_marker(devanagari_text)

    if not devanagari_marker:
        # No marker in source, return as-is
        return transliteration

    # Remove ASCII verse markers from transliteration (|| X-Y ||)
    transliteration = re.sub(r'\|\|\s*\d+(?:-\d+)?\s*\|\|', '', transliteration)

    # Check if transliteration already has Devanagari marker
    if devanagari_marker in transliteration:
        return transliteration.strip()

    # Remove any existing Devanagari markers that might be different
    transliteration = re.sub(r'॥\s*[०-९\d]+(?:-[०-९\d]+)?\s*॥', '', transliteration)

    # Append the correct Devanagari marker
    return f"{transliteration.strip()} {devanagari_marker}".strip()


def generate_verse_content(devanagari_text: str, collection: str, verse_id: str = None,
                          dry_run: bool = False, cost_tracker: CostTracker = None) -> Tuple[dict, float]:
    """
    Generate AI content (transliteration, meaning, translation, story) from Devanagari text.

    Args:
        devanagari_text: The canonical Devanagari verse text
        collection: Collection key for context
        verse_id: Verse identifier (e.g., chaupai_02, shloka_01)
        dry_run: If True, skip API call and return mock data
        cost_tracker: CostTracker instance to record API costs

    Returns:
        Tuple of (content_dict, cost)
    """
    if dry_run:
        print("  → [DRY-RUN] Would generate AI content from canonical text...", file=sys.stderr)
        mock_result = {
            "devanagari": devanagari_text,
            "transliteration": "[mock transliteration]",
            "title_en": "[Mock Title]",
            "title_hi": "[नकली शीर्षक]",
            "phonetic_notes": [],
            "word_meanings": [],
            "meaning": "[mock word-by-word meaning]",
            "literal_translation": {"en": "[mock literal translation]", "hi": "[नकली शाब्दिक अनुवाद]"},
            "interpretive_meaning": {"en": "[mock interpretive meaning]", "hi": "[नकली व्याख्यात्मक अर्थ]"},
            "story": {"en": "[mock story]", "hi": "[नकली कथा]"},
            "practical_application": {
                "teaching": {"en": "[mock teaching]", "hi": "[नकली शिक्षा]"},
                "when_to_use": {"en": "[mock when to use]", "hi": "[नकली उपयोग]"}
            },
            "translation": {"en": "[mock translation]"}
        }
        return mock_result, 0.0

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise UserFriendlyError(
            "OPENAI_API_KEY environment variable not set",
            [
                "Set the OPENAI_API_KEY environment variable with your OpenAI API key",
                "Get an API key from: https://platform.openai.com/api-keys",
                "Add to your .env file: OPENAI_API_KEY=sk-..."
            ]
        )

    client = OpenAI(api_key=api_key)

    prompt = f"""You are an expert in Sanskrit/Hindi spiritual texts. Given this verse from {collection}:

Devanagari: {devanagari_text}
Verse ID: {verse_id or 'unknown'}

Please provide complete verse analysis in the following format:

1. VERSE TITLE (short, descriptive - 3-6 words capturing the essence):
English: [Title in English]
Hindi: [शीर्षक हिंदी में]

2. TRANSLITERATION (IAST format, single line, precisely matching the Devanagari):
IMPORTANT: If the Devanagari text includes verse markers (॥ digits ॥), preserve them EXACTLY as they appear.
[Your transliteration here]

3. PHONETIC NOTES (for 2-3 key words that may be difficult to pronounce):
CRITICAL: Only include words that ACTUALLY APPEAR in the Devanagari text above.
Format each as:
PHONETIC: [Devanagari word from verse] | PRONUNCIATION: [syllable-by-syllable] | EMPHASIS: [which syllable]

Example (only if these words appear in the verse):
PHONETIC: हनुमंत | PRONUNCIATION: ha-nu-mant | EMPHASIS: first syllable
PHONETIC: परिखेहु | PRONUNCIATION: pa-ri-khe-hu | EMPHASIS: third syllable

4. WORD-BY-WORD MEANINGS (structured list of ALL key words):
Format each word exactly as:
WORD: [Devanagari word] | ROMAN: [romanization] | EN: [English meaning] | HI: [Hindi meaning]

Example:
WORD: तब | ROMAN: Tab | EN: then/until then | HI: तब/तब तक
WORD: लगि | ROMAN: Lagi | EN: until | HI: तक

5. WORD-BY-WORD BREAKDOWN (plain text explanation):
[Simple word-by-word meaning explanation]

6. LITERAL TRANSLATION:
English: [Direct, literal translation]
Hindi: [शाब्दिक अनुवाद]

7. INTERPRETIVE MEANING (deeper spiritual/contextual explanation):
English: [2-3 sentences explaining the deeper meaning]
Hindi: [गहरा अर्थ 2-3 वाक्य]

8. STORY & CONTEXT:
English: [2-3 paragraphs explaining context, significance, and narrative]
Hindi: [संदर्भ और कथा 2-3 पैराग्राफ]

9. PRACTICAL APPLICATION:
Teaching (English): [Core teaching in 1-2 sentences]
Teaching (Hindi): [मुख्य शिक्षा 1-2 वाक्य]
When to Use (English): [When to recite/apply this verse]
When to Use (Hindi): [कब उपयोग करें]

Format your response exactly as above with clear section headers."""

    try:
        print("  → Generating AI content from canonical text...", file=sys.stderr)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in Sanskrit and Hindi spiritual texts, providing accurate transliterations, translations, and meaningful interpretations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3  # Lower temperature for more consistent, accurate results
        )

        content = response.choices[0].message.content

        # Track cost
        cost = 0.0
        if cost_tracker and hasattr(response, 'usage'):
            cost = cost_tracker.track_gpt4(
                'content_generation',
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )

        # Parse the response into structured fields (complete chaupai format)
        result = {
            "devanagari": devanagari_text,
            "transliteration": "",
            "title_en": "",
            "title_hi": "",
            "phonetic_notes": [],
            "word_meanings": [],
            "meaning": "",
            "literal_translation": {"en": "", "hi": ""},
            "interpretive_meaning": {"en": "", "hi": ""},
            "story": {"en": "", "hi": ""},
            "practical_application": {
                "teaching": {"en": "", "hi": ""},
                "when_to_use": {"en": "", "hi": ""}
            },
            "translation": {"en": ""}  # For backward compatibility
        }

        # Parse sections
        lines = content.split("\n")
        current_section = None
        current_lang = None

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Section headers
            if "VERSE TITLE" in line.upper() or line.strip() == "1.":
                current_section = "title"
            elif "TRANSLITERATION" in line.upper() or line.strip() == "2.":
                current_section = "transliteration"
            elif "PHONETIC NOTES" in line.upper() or line.strip() == "3.":
                current_section = "phonetic_notes"
            elif "WORD-BY-WORD MEANINGS" in line.upper() or line.strip() == "4.":
                current_section = "word_meanings"
            elif "WORD-BY-WORD BREAKDOWN" in line.upper() or line.strip() == "5.":
                current_section = "meaning"
            elif "LITERAL TRANSLATION" in line.upper() or line.strip() == "6.":
                current_section = "literal_translation"
            elif "INTERPRETIVE MEANING" in line.upper() or line.strip() == "7.":
                current_section = "interpretive_meaning"
            elif "STORY" in line.upper() or line.strip() == "8.":
                current_section = "story"
            elif "PRACTICAL APPLICATION" in line.upper() or line.strip() == "9.":
                current_section = "practical_application"
            # Language indicators
            elif line_stripped.startswith("English:"):
                current_lang = "en"
                text = line_stripped[8:].strip()
                if current_section == "title" and text:
                    result["title_en"] = text
                elif current_section == "literal_translation" and text:
                    result["literal_translation"]["en"] = text
                elif current_section == "interpretive_meaning" and text:
                    result["interpretive_meaning"]["en"] = text
                elif current_section == "story" and text:
                    result["story"]["en"] = text
            elif line_stripped.startswith("Hindi:") or line_stripped.startswith("हिंदी:"):
                current_lang = "hi"
                text = line_stripped.split(":", 1)[1].strip()
                if current_section == "title" and text:
                    result["title_hi"] = text
                elif current_section == "literal_translation" and text:
                    result["literal_translation"]["hi"] = text
                elif current_section == "interpretive_meaning" and text:
                    result["interpretive_meaning"]["hi"] = text
                elif current_section == "story" and text:
                    result["story"]["hi"] = text
            elif "Teaching" in line and "English" in line:
                text = line.split(":", 1)[1].strip() if ":" in line else ""
                result["practical_application"]["teaching"]["en"] = text
            elif "Teaching" in line and ("Hindi" in line or "हिंदी" in line):
                text = line.split(":", 1)[1].strip() if ":" in line else ""
                result["practical_application"]["teaching"]["hi"] = text
            elif "When to Use" in line and "English" in line:
                text = line.split(":", 1)[1].strip() if ":" in line else ""
                result["practical_application"]["when_to_use"]["en"] = text
            elif "When to Use" in line and ("Hindi" in line or "कब" in line):
                text = line.split(":", 1)[1].strip() if ":" in line else ""
                result["practical_application"]["when_to_use"]["hi"] = text
            # Content lines
            elif current_section == "transliteration" and line_stripped and not any(x in line.upper() for x in ["TRANSLITERATION", "2."]):
                result["transliteration"] = line_stripped
            elif current_section == "phonetic_notes" and line_stripped and "PHONETIC:" in line_stripped:
                # Parse phonetic note entry: PHONETIC: word | PRONUNCIATION: syllables | EMPHASIS: which
                try:
                    parts = line_stripped.split("|")
                    if len(parts) >= 3:
                        word = ""
                        phonetic = ""
                        emphasis = ""

                        for part in parts:
                            part = part.strip()
                            if part.startswith("PHONETIC:"):
                                word = part[9:].strip()
                            elif part.startswith("PRONUNCIATION:"):
                                phonetic = part[14:].strip()
                            elif part.startswith("EMPHASIS:"):
                                emphasis = part[9:].strip()

                        if word and phonetic:
                            # Validate that the word exists in the devanagari text
                            if word in devanagari_text:
                                result["phonetic_notes"].append({
                                    "word": word,
                                    "phonetic": phonetic,
                                    "emphasis": emphasis
                                })
                            else:
                                print(f"  ⚠ Warning: Skipping phonetic note for '{word}' - not found in verse", file=sys.stderr)
                except Exception:
                    print(f"  ⚠ Warning: Failed to parse phonetic note: {line_stripped}", file=sys.stderr)
                    pass  # Skip malformed entries
            elif current_section == "word_meanings" and line_stripped and "WORD:" in line_stripped:
                # Parse word meaning entry: WORD: ... | ROMAN: ... | EN: ... | HI: ...
                try:
                    parts = line_stripped.split("|")
                    if len(parts) >= 4:
                        word = ""
                        roman = ""
                        meaning_en = ""
                        meaning_hi = ""

                        for part in parts:
                            part = part.strip()
                            if part.startswith("WORD:"):
                                word = part[5:].strip()
                            elif part.startswith("ROMAN:"):
                                roman = part[6:].strip()
                            elif part.startswith("EN:"):
                                meaning_en = part[3:].strip()
                            elif part.startswith("HI:"):
                                meaning_hi = part[3:].strip()

                        if word and roman:
                            result["word_meanings"].append({
                                "word": word,
                                "roman": roman,
                                "meaning": {
                                    "en": meaning_en,
                                    "hi": meaning_hi
                                }
                            })
                except Exception:
                    pass  # Skip malformed entries
            elif current_section == "meaning" and line_stripped and not any(x in line.upper() for x in ["BREAKDOWN", "4."]):
                result["meaning"] += line_stripped + " "
            elif current_section == "literal_translation" and current_lang == "en" and "English:" not in line:
                result["literal_translation"]["en"] += " " + line_stripped
            elif current_section == "literal_translation" and current_lang == "hi" and "Hindi:" not in line:
                result["literal_translation"]["hi"] += " " + line_stripped
            elif current_section == "interpretive_meaning" and current_lang == "en" and "English:" not in line:
                result["interpretive_meaning"]["en"] += " " + line_stripped
            elif current_section == "interpretive_meaning" and current_lang == "hi" and "Hindi:" not in line:
                result["interpretive_meaning"]["hi"] += " " + line_stripped
            elif current_section == "story" and current_lang == "en" and "English:" not in line:
                result["story"]["en"] += " " + line_stripped
            elif current_section == "story" and current_lang == "hi" and "Hindi:" not in line:
                result["story"]["hi"] += " " + line_stripped

        # Clean up whitespace
        result["meaning"] = result["meaning"].strip()
        result["literal_translation"]["en"] = result["literal_translation"]["en"].strip()
        result["literal_translation"]["hi"] = result["literal_translation"]["hi"].strip()
        result["interpretive_meaning"]["en"] = result["interpretive_meaning"]["en"].strip()
        result["interpretive_meaning"]["hi"] = result["interpretive_meaning"]["hi"].strip()
        result["story"]["en"] = result["story"]["en"].strip()
        result["story"]["hi"] = result["story"]["hi"].strip()

        # Set translation.en for backward compatibility (use literal or interpretive)
        result["translation"]["en"] = result["literal_translation"]["en"] or result["interpretive_meaning"]["en"]

        # Normalize transliteration markers (ensure Devanagari markers are consistent)
        if result["transliteration"]:
            result["transliteration"] = normalize_transliteration_markers(
                result["transliteration"],
                devanagari_text
            )

        print("  ✓ Generated complete verse content with titles, translations, story, and practical applications", file=sys.stderr)
        return result, cost

    except Exception as e:
        if DEBUG_MODE:
            import traceback
            traceback.print_exc()
        raise UserFriendlyError(
            f"Failed to generate verse content: {str(e)}",
            [
                "Check your OPENAI_API_KEY is valid and has available credits",
                "Verify the Devanagari text is properly formatted",
                "Try again in a few moments if this is a temporary API issue",
                "Use --debug flag to see full error details"
            ]
        )


def format_title_with_prefix(title: str, verse_type: str, verse_number: int, lang: str = 'en') -> str:
    """
    Format a title with verse type and number prefix.

    Args:
        title: Base descriptive title (e.g., "Ocean of Knowledge")
        verse_type: Type of verse (e.g., 'shloka', 'chaupai', 'doha', 'verse')
        verse_number: Sequence number for display
        lang: Language code ('en' or 'hi')

    Returns:
        Formatted title with prefix (e.g., "Shloka 1: Ocean of Knowledge")
    """
    # Verse type translations
    verse_type_labels = {
        'en': {
            'shloka': 'Shloka',
            'chaupai': 'Chaupai',
            'doha': 'Doha',
            'verse': 'Verse',
            'mantra': 'Mantra',
            'stanza': 'Stanza',
        },
        'hi': {
            'shloka': 'श्लोक',
            'chaupai': 'चौपाई',
            'doha': 'दोहा',
            'verse': 'पद',
            'mantra': 'मंत्र',
            'stanza': 'पद',
        }
    }

    # Get the label for this verse type, fallback to capitalized verse_type
    verse_label = verse_type_labels.get(lang, {}).get(verse_type.lower(), verse_type.title())

    # If title already starts with the verse type prefix, return as-is
    if title.startswith(f"{verse_label} {verse_number}:"):
        return title

    # Format: "Shloka 1: Title" or "श्लोक 1: शीर्षक"
    return f"{verse_label} {verse_number}: {title}"


def create_verse_file_with_content(verse_file: Path, content: dict, collection: str, verse_num: int, verse_id: str = None, project_dir: Path = None) -> bool:
    """
    Create a new verse markdown file with generated content in complete chaupai format.

    Args:
        verse_file: Path to the verse markdown file to create
        content: Dictionary with generated content fields
        collection: Collection key
        verse_num: Verse number (for display, not navigation)
        verse_id: Verse identifier (e.g., chaupai-02, shloka-01)
        project_dir: Project directory (for reading sequence)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure parent directory exists
        verse_file.parent.mkdir(parents=True, exist_ok=True)

        # Extract verse_id from filename if not provided
        if not verse_id:
            verse_id = verse_file.stem  # e.g., chaupai-02 from chaupai-02.md

        # Determine verse type and extract number from ID
        verse_type = verse_id.split('-')[0] if '-' in verse_id else 'verse'  # chaupai, shloka, doha, etc.
        id_number = extract_verse_number_from_id(verse_id) or verse_num

        # Extract chapter number for Bhagavad Gita format (chapter-XX-verse-YY)
        chapter_number = None
        if 'chapter-' in verse_id:
            chapter_match = re.search(r'chapter-(\d+)', verse_id)
            if chapter_match:
                chapter_number = int(chapter_match.group(1))

        # Get navigation from sequence
        if project_dir is None:
            project_dir = verse_file.parent.parent.parent  # Go up from _verses/collection/file.md
        prev_id, next_id = get_navigation_from_sequence(collection, verse_id, project_dir)

        # Format titles with verse type and number prefix
        title_en_base = content.get('title_en', '')
        title_hi_base = content.get('title_hi', '')

        # Add prefix if title exists, otherwise use default format
        if title_en_base:
            title_en = format_title_with_prefix(title_en_base, verse_type, id_number, 'en')
        else:
            title_en = f'{verse_type.title()} {id_number}'

        if title_hi_base:
            title_hi = format_title_with_prefix(title_hi_base, verse_type, id_number, 'hi')
        else:
            title_hi = f'{verse_type} {id_number}'

        # section_verse_number: position within verse type section, derived from the
        # numeric suffix of the verse ID (chaupai-01 → 1, doha-closing → None).
        section_verse_number = extract_verse_number_from_id(verse_id)

        # Build complete frontmatter (chaupai format)
        frontmatter = {
            'layout': 'verse',
            'collection_key': collection,
            'permalink': f'/{collection}/{verse_id}/',
            'title_en': title_en,
            'title_hi': title_hi,
            'chapter': chapter_number,  # Will be removed if None
            'verse_number': verse_num,
            'section_verse_number': section_verse_number,  # Will be removed if None
            'verse_type': verse_type,
            'previous_verse': f'/{collection}/{prev_id}/' if prev_id else None,
            'next_verse': f'/{collection}/{next_id}/' if next_id else get_collection_permalink(collection, project_dir),
            'image': f'/images/{collection}/modern-minimalist/{verse_id}.png',
            'devanagari': content['devanagari'],
            'transliteration': content['transliteration'],
            'phonetic_notes': content.get('phonetic_notes', []),
            'word_meanings': content.get('word_meanings', []),
            'literal_translation': content.get('literal_translation', {'en': '', 'hi': ''}),
            'interpretive_meaning': content.get('interpretive_meaning', {'en': '', 'hi': ''}),
            'story': content.get('story', {'en': '', 'hi': ''}),
            'practical_application': content.get('practical_application', {
                'teaching': {'en': '', 'hi': ''},
                'when_to_use': {'en': '', 'hi': ''}
            }),
            'meaning': content.get('meaning', ''),
            'translation': content.get('translation', {'en': ''})
        }

        # Remove None values
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None}

        # Build file content
        file_content = "---\n"
        file_content += yaml.dump(frontmatter, allow_unicode=True, sort_keys=False, default_flow_style=False)
        file_content += "---\n"

        # Add body sections (minimal, most content is in frontmatter)
        # Only add if story/practical_application are strings (legacy format)
        if isinstance(content.get('story'), str) and content.get('story'):
            file_content += f"\n## Story & Context\n\n{content['story']}\n"

        if isinstance(content.get('practical_applications'), str) and content.get('practical_applications'):
            file_content += f"\n## Practical Applications\n\n{content['practical_applications']}\n"

        # Write file
        with open(verse_file, 'w', encoding='utf-8') as f:
            f.write(file_content)

        print(f"  ✓ Created verse file: {verse_file.name}", file=sys.stderr)
        return True

    except Exception as e:
        print(f"  ✗ Error creating verse file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def update_previous_verse_navigation(collection: str, current_verse_id: str, project_dir: Path = Path.cwd()) -> bool:
    """
    Update the previous verse's next_verse field to point to the current verse.

    Args:
        collection: Collection key
        current_verse_id: Current verse ID
        project_dir: Project directory

    Returns:
        True if successful or not needed, False if failed
    """
    # Get previous verse ID from sequence
    prev_id, _ = get_navigation_from_sequence(collection, current_verse_id, project_dir)
    if not prev_id:
        # No previous verse, nothing to update
        return True

    # Find the previous verse file
    verses_dir = project_dir / "_verses" / collection
    prev_verse_file = verses_dir / f"{prev_id}.md"

    if not prev_verse_file.exists():
        # Previous verse file doesn't exist yet, skip
        return True

    try:
        # Read the previous verse file
        with open(prev_verse_file, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.startswith('---'):
            return True

        parts = content.split('---', 2)
        if len(parts) < 3:
            return True

        frontmatter = yaml.safe_load(parts[1]) or {}
        body = parts[2]

        # Update next_verse to point to current verse
        frontmatter['next_verse'] = f'/{collection}/{current_verse_id}/'

        # Write back
        frontmatter_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
        updated_content = f"---\n{frontmatter_str}---{body}"

        with open(prev_verse_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        print(f"  ✓ Updated previous verse ({prev_id}) navigation")
        return True

    except Exception as e:
        print(f"  ⚠ Warning: Could not update previous verse navigation: {e}", file=sys.stderr)
        return False


def update_verse_file_with_content(verse_file: Path, content: dict) -> bool:
    """
    Update verse markdown file with generated content.

    Args:
        verse_file: Path to the verse markdown file
        content: Dictionary with generated content fields

    Returns:
        True if successful, False otherwise
    """
    if not verse_file.exists():
        print(f"  ✗ Verse file not found: {verse_file}", file=sys.stderr)
        return False

    try:
        # Read existing file
        with open(verse_file, 'r', encoding='utf-8') as f:
            file_content = f.read()

        # Parse frontmatter and body
        if not file_content.startswith('---'):
            print(f"  ✗ Invalid verse file format (no frontmatter): {verse_file}", file=sys.stderr)
            return False

        parts = file_content.split('---', 2)
        if len(parts) < 3:
            print(f"  ✗ Invalid verse file format (incomplete frontmatter): {verse_file}", file=sys.stderr)
            return False

        frontmatter = yaml.safe_load(parts[1]) or {}
        body = parts[2]

        # Get verse info from existing frontmatter or filename
        verse_num = frontmatter.get('verse_number', 0)
        collection = frontmatter.get('collection_key') or frontmatter.get('collection', 'unknown')
        verse_id = verse_file.stem  # e.g., shloka-02
        verse_type = verse_id.split('-')[0] if '-' in verse_id else 'verse'
        id_number = extract_verse_number_from_id(verse_id) or verse_num

        # Get navigation from sequence
        project_dir = verse_file.parent.parent.parent  # Go up from _verses/collection/file.md
        prev_id, next_id = get_navigation_from_sequence(collection, verse_id, project_dir)

        # Format titles with verse type and number prefix
        title_en_base = content.get('title_en') or frontmatter.get('title_en', '')
        title_hi_base = content.get('title_hi') or frontmatter.get('title_hi', '')

        # Add prefix if title exists, otherwise use default format
        if title_en_base:
            title_en = format_title_with_prefix(title_en_base, verse_type, id_number, 'en')
        else:
            title_en = f'{verse_type.title()} {id_number}'

        if title_hi_base:
            title_hi = format_title_with_prefix(title_hi_base, verse_type, id_number, 'hi')
        else:
            title_hi = f'{verse_type} {id_number}'

        # Update frontmatter with ALL generated content (complete chaupai format)
        # Preserve existing metadata fields but add/update with new structure
        frontmatter.update({
            'layout': frontmatter.get('layout', 'verse'),
            'collection_key': collection,  # Use collection_key, not just collection
            'permalink': frontmatter.get('permalink', f'/{collection}/{verse_id}/'),
            'title_en': title_en,
            'title_hi': title_hi,
            'verse_number': verse_num,
            'verse_type': verse_type,
            'previous_verse': f'/{collection}/{prev_id}/' if prev_id else None,
            'next_verse': f'/{collection}/{next_id}/' if next_id else get_collection_permalink(collection, project_dir),
            'image': frontmatter.get('image', f'/images/{collection}/modern-minimalist/{verse_id}.png'),
            'devanagari': content['devanagari'],
            'transliteration': content['transliteration'],
            'phonetic_notes': content.get('phonetic_notes', frontmatter.get('phonetic_notes', [])),
            'word_meanings': content.get('word_meanings', frontmatter.get('word_meanings', [])),
            'literal_translation': content.get('literal_translation', {'en': '', 'hi': ''}),
            'interpretive_meaning': content.get('interpretive_meaning', {'en': '', 'hi': ''}),
            'story': content.get('story', {'en': '', 'hi': ''}),
            'practical_application': content.get('practical_application', {
                'teaching': {'en': '', 'hi': ''},
                'when_to_use': {'en': '', 'hi': ''}
            }),
            'meaning': content.get('meaning', ''),
            'translation': content.get('translation', {'en': ''})
        })

        # Remove None values and old 'collection' field
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None and k != 'collection'}

        # Build updated content
        updated_content = "---\n"
        updated_content += yaml.dump(frontmatter, allow_unicode=True, sort_keys=False, default_flow_style=False)
        updated_content += "---"

        # Remove body sections (everything should be in frontmatter now for complete format)
        # Only keep body if there's custom content beyond standard sections
        updated_content += "\n"

        # Write updated file
        with open(verse_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        print(f"  ✓ Updated verse file: {verse_file.name}", file=sys.stderr)
        return True

    except Exception as e:
        print(f"  ✗ Error updating verse file: {e}", file=sys.stderr)
        return False


def find_command(command_name: str) -> str:
    """Find the full path to a command, checking common locations."""
    # First, try to find command in the same directory as current Python executable
    # This ensures we use commands from the same virtual environment
    python_executable = Path(sys.executable)
    bin_dir = python_executable.parent
    cmd_in_venv = bin_dir / command_name

    if cmd_in_venv.exists():
        return str(cmd_in_venv)

    # Try shutil.which (checks PATH)
    cmd_path = shutil.which(command_name)
    if cmd_path:
        return cmd_path

    # Check common installation locations
    common_paths = [
        Path.home() / "Library" / "Python" / "3.13" / "bin" / command_name,
        Path.home() / "Library" / "Python" / "3.12" / "bin" / command_name,
        Path.home() / "Library" / "Python" / "3.11" / "bin" / command_name,
        Path.home() / ".local" / "bin" / command_name,
        Path("/usr/local/bin") / command_name,
    ]

    for path in common_paths:
        if path.exists():
            return str(path)

    # If not found, return command name and hope it's in PATH
    return command_name


def validate_collection(collection: str, project_dir: Path = Path.cwd()) -> bool:
    """Validate that collection exists and is enabled."""
    # Check _verses directory
    verses_dir = project_dir / "_verses" / collection
    if not verses_dir.exists():
        print(f"✗ Error: Collection directory not found: {verses_dir}")
        return False

    # Check collections.yml
    collections_file = project_dir / "_data" / "collections.yml"
    if collections_file.exists():
        with open(collections_file) as f:
            data = yaml.safe_load(f)
            if collection not in data:
                print(f"✗ Error: Collection '{collection}' not found in collections.yml")
                return False
            if not data[collection].get('enabled', False):
                print(f"✗ Error: Collection '{collection}' is disabled in collections.yml")
                return False

    return True


def list_collections(project_dir: Path = Path.cwd()):
    """List available collections from _data/collections.yml"""
    collections_file = project_dir / "_data" / "collections.yml"
    if not collections_file.exists():
        print("No collections.yml found")
        return []

    with open(collections_file) as f:
        data = yaml.safe_load(f)
        enabled = [
            (key, info.get('name', {}).get('en', key))
            for key, info in data.items()
            if info.get('enabled', False)
        ]

    print("\nAvailable collections:")
    for key, name in enabled:
        verses_dir = project_dir / "_verses" / key
        count = len(list(verses_dir.glob("*.md"))) if verses_dir.exists() else 0
        print(f"  ✓ {key:30s} - {name} ({count} verses)")

    return enabled


def get_verse_sequence(collection: str, project_dir: Path = Path.cwd()) -> tuple[Optional[list], str]:
    """
    Read the verse sequence from the data file.

    Supports multiple formats:
    1. _meta.sequence - explicit list of verse IDs
    2. Bhagavad Gita format - generates sequence from chapter structure
    3. Fallback - extracts verse IDs from YAML keys (excluding _meta)

    Args:
        collection: Collection key (e.g., "sundar-kaand", "bhagavad-gita")
        project_dir: Project directory (defaults to current working directory)

    Returns:
        Tuple of (sequence_list, source) where source is:
        - "explicit" if from _meta.sequence
        - "bhagavad-gita-auto" if auto-generated from BG structure
        - "yaml-keys" if extracted from YAML keys
        - None if not found
    """
    # Look for data file - try .yaml first, then .yml
    data_file = project_dir / "data" / "verses" / f"{collection}.yaml"
    if not data_file.exists():
        data_file = project_dir / "data" / "verses" / f"{collection}.yml"

    if not data_file.exists():
        return None, None

    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            return None, None

        # Method 1: Check for explicit _meta.sequence
        if '_meta' in data and isinstance(data['_meta'], dict):
            sequence = data['_meta'].get('sequence')
            if sequence and isinstance(sequence, list):
                return sequence, "explicit"

            # Method 2: Check for Bhagavad Gita chapter structure
            # Format: chapter-XX-verse-YY with known chapter verse counts
            if data['_meta'].get('chapters') and data['_meta'].get('total_verses'):
                # Bhagavad Gita: 18 chapters with specific verse counts
                chapter_verse_counts = {
                    1: 47, 2: 72, 3: 43, 4: 42, 5: 29, 6: 47,
                    7: 30, 8: 28, 9: 34, 10: 42, 11: 55, 12: 20,
                    13: 35, 14: 27, 15: 20, 16: 24, 17: 28, 18: 78
                }

                sequence = []
                for chapter in range(1, data['_meta']['chapters'] + 1):
                    verse_count = chapter_verse_counts.get(chapter, 0)
                    if verse_count == 0:
                        # If we don't have the count, try to infer from existing verses
                        # or skip this chapter
                        continue

                    for verse in range(1, verse_count + 1):
                        verse_id = f"chapter-{chapter:02d}-verse-{verse:02d}"
                        sequence.append(verse_id)

                if sequence:
                    return sequence, "bhagavad-gita-auto"

        # Method 3: Fallback - extract verse IDs from YAML keys (sorted)
        verse_ids = [k for k in data.keys() if not k.startswith('_')]
        if verse_ids:
            # Sort by extracting numbers from verse IDs
            def sort_key(verse_id):
                numbers = re.findall(r'\d+', verse_id)
                return [int(n) for n in numbers]

            verse_ids.sort(key=sort_key)
            return verse_ids, "yaml-keys"

        return None, None

    except Exception as e:
        print(f"Warning: Error reading sequence from {data_file}: {e}", file=sys.stderr)
        return None, None


def extract_verse_number_from_id(verse_id: str) -> Optional[int]:
    """
    Extract the number from a verse ID.

    Args:
        verse_id: Verse ID like "chaupai-16", "doha-03", "shloka-01"

    Returns:
        The number from the ID, or None if not found
    """
    match = re.search(r'[-_](\d+)$', verse_id)
    if match:
        return int(match.group(1))
    return None


def get_collection_permalink(collection: str, project_dir: Path = Path.cwd()) -> str:
    """
    Return the collection index URL for use as next_verse on the last verse.
    Reads permalink_base from _data/collections.yml, defaults to /{collection}/.
    """
    collections_file = project_dir / "_data" / "collections.yml"
    if collections_file.exists():
        try:
            with open(collections_file) as f:
                data = yaml.safe_load(f) or {}
            base = data.get(collection, {}).get("permalink_base")
            if base:
                return base if base.endswith("/") else base + "/"
        except Exception:
            pass
    return f"/{collection}/"


def get_navigation_from_sequence(collection: str, verse_id: str, project_dir: Path = Path.cwd()) -> tuple[Optional[str], Optional[str]]:
    """
    Get previous and next verse IDs from the sequence.

    Only returns verse IDs if the corresponding verse files exist to prevent
    navigation links to non-existent verses (404 errors).

    Args:
        collection: Collection key
        verse_id: Current verse ID
        project_dir: Project directory

    Returns:
        Tuple of (previous_verse_id, next_verse_id), None if not found or file doesn't exist
    """
    sequence, _ = get_verse_sequence(collection, project_dir)
    if not sequence:
        return None, None

    try:
        idx = sequence.index(verse_id)
        prev_id = sequence[idx - 1] if idx > 0 else None
        next_id = sequence[idx + 1] if idx < len(sequence) - 1 else None

        # Check if verse files actually exist before returning IDs
        verses_dir = project_dir / "_verses" / collection

        # Only return prev_id if the file exists
        if prev_id:
            prev_file = verses_dir / f"{prev_id}.md"
            if not prev_file.exists():
                prev_id = None

        # Only return next_id if the file exists
        if next_id:
            next_file = verses_dir / f"{next_id}.md"
            if not next_file.exists():
                next_id = None

        return prev_id, next_id
    except ValueError:
        # verse_id not in sequence
        return None, None


def validate_generation_requirements(
    collection: str,
    verse_id: str,
    generate_image: bool,
    generate_audio: bool,
    regenerate_content: bool,
    update_embeddings: bool,
    project_dir: Path = Path.cwd()
) -> tuple[bool, list[str]]:
    """
    Validate all requirements before starting generation.

    Args:
        collection: Collection key
        verse_id: Verse ID to generate
        generate_image: Whether image generation is requested
        generate_audio: Whether audio generation is requested
        regenerate_content: Whether content regeneration is requested
        update_embeddings: Whether embeddings update is requested
        project_dir: Project directory

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # 1. Check collection exists (use same path as list_collections)
    collections_file = project_dir / "_data" / "collections.yml"

    if collections_file.exists():
        try:
            with open(collections_file, 'r', encoding='utf-8') as f:
                collections_data = yaml.safe_load(f)
            # Check if collection exists as a direct key (matching list_collections structure)
            if collections_data and collection not in collections_data:
                errors.append(f"Collection '{collection}' not found in _data/collections.yml")
            # Check if collection is enabled
            elif collections_data and not collections_data.get(collection, {}).get('enabled', False):
                errors.append(f"Collection '{collection}' is disabled in _data/collections.yml")
        except Exception as e:
            errors.append(f"Error reading _data/collections.yml: {e}")
    else:
        # Collections file is optional - just warn
        pass

    # 2. Check verse exists in data file
    data_file = project_dir / "data" / "verses" / f"{collection}.yaml"
    if not data_file.exists():
        data_file = project_dir / "data" / "verses" / f"{collection}.yml"

    verse_in_data = False
    if data_file.exists():
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                verses_data = yaml.safe_load(f)
            if verses_data and verse_id in verses_data:
                verse_data = verses_data[verse_id]
                if isinstance(verse_data, dict) and 'devanagari' in verse_data:
                    verse_in_data = True
                elif isinstance(verse_data, str):
                    verse_in_data = True
                else:
                    errors.append(f"Verse '{verse_id}' exists but missing 'devanagari' field")
            else:
                errors.append(f"Verse '{verse_id}' not found in {data_file.name}")
        except Exception as e:
            errors.append(f"Error reading {data_file.name}: {e}")
    else:
        errors.append(f"Data file not found: data/verses/{collection}.yaml")

    # 3. Check API keys
    if generate_image or regenerate_content or update_embeddings:
        if not os.getenv("OPENAI_API_KEY"):
            errors.append("OPENAI_API_KEY not set (required for image/content/embeddings)")

    if generate_audio:
        if not os.getenv("ELEVENLABS_API_KEY"):
            errors.append("ELEVENLABS_API_KEY not set (required for audio)")

    # 4. Check scene description exists (warning only, not fatal)
    if generate_image and verse_in_data:
        if not validate_scene_description_exists(collection, verse_id, project_dir):
            # This is just a warning - we can generate it
            print(f"  ⚠ Warning: Scene description not found for {verse_id} (will be generated)")

    # 5. Check verses directory exists
    verses_dir = project_dir / "_verses" / collection
    if not verses_dir.exists():
        try:
            verses_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create verses directory: {e}")

    return len(errors) == 0, errors


def find_next_verse(collection: str, project_dir: Path = Path.cwd()) -> Optional[int]:
    """
    Find the next verse position to generate.

    Requires a canonical YAML file (data/verses/<collection>.yaml) to exist.
    Finds the first missing verse in the sequence.

    Returns:
        Next verse position (1-based) to generate, or None if canonical file missing
    """
    # Get verse sequence and its source
    sequence, source = get_verse_sequence(collection, project_dir)
    if not sequence:
        print("✗ Error: Cannot use --next without canonical verse file", file=sys.stderr)
        print("", file=sys.stderr)
        print(f"The --next flag requires data/verses/{collection}.yaml to determine verse sequence.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print(f"  1. Create canonical file: verse-add --collection {collection} --verse 1-10", file=sys.stderr)
        print("  2. Run verse-validate --fix to create template", file=sys.stderr)
        print(f"  3. Use explicit verse number: verse-generate --collection {collection} --verse 1", file=sys.stderr)
        return None

    # Warn if sequence was auto-generated (not explicit)
    if source != "explicit":
        print(f"⚠️  Warning: No explicit _meta.sequence found in data/verses/{collection}.yaml", file=sys.stderr)
        print("", file=sys.stderr)

        if source == "bhagavad-gita-auto":
            print("Using auto-generated sequence for Bhagavad Gita (18 chapters, 700 verses).", file=sys.stderr)
        elif source == "yaml-keys":
            print("Using sequence extracted from existing verse IDs in YAML file.", file=sys.stderr)

        print("", file=sys.stderr)
        print("To avoid this warning, add _meta.sequence to your YAML file:", file=sys.stderr)
        print("", file=sys.stderr)
        print("  _meta:", file=sys.stderr)
        print("    sequence:", file=sys.stderr)
        print("      - chapter-01-verse-01", file=sys.stderr)
        print("      - chapter-01-verse-02", file=sys.stderr)
        print("      - ...", file=sys.stderr)
        print("", file=sys.stderr)

        # Ask for confirmation
        try:
            response = input("Continue with auto-generated sequence? (y/n): ").strip().lower()
            if response not in ['y', 'yes']:
                print("Cancelled.", file=sys.stderr)
                return None
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.", file=sys.stderr)
            return None

        print("")  # Add spacing after confirmation

    # Find which verses in the sequence already have files
    verses_dir = project_dir / "_verses" / collection
    if not verses_dir.exists():
        return 1  # Start from position 1

    # Check each position in the sequence
    for position, verse_id in enumerate(sequence, start=1):
        # Check if file exists for this verse_id
        verse_file = verses_dir / f"{verse_id}.md"
        if not verse_file.exists():
            # Found first missing verse
            return position

    # All verses in sequence exist - next would be beyond the sequence
    print(f"✓ All {len(sequence)} verses in sequence already exist!", file=sys.stderr)
    print("", file=sys.stderr)
    print("Options:", file=sys.stderr)
    print(f"  1. Add more verses to data/verses/{collection}.yaml", file=sys.stderr)
    print(f"  2. Regenerate existing verse: verse-generate --collection {collection} --verse 1 --regenerate", file=sys.stderr)
    return None


def infer_verse_id(collection: str, verse_position: int, project_dir: Path = Path.cwd()) -> Optional[str]:
    """
    Infer verse ID from verse position.

    If a data file with sequence exists, maps position to verse_id from the sequence.
    Otherwise, falls back to scanning existing verse files.

    Args:
        collection: Collection key
        verse_position: Position in the sequence (1-based index)
        project_dir: Project directory

    Returns:
        - The verse_id at the given position
        - None if position is invalid or data is missing
    """
    # Try to use sequence from data file
    sequence, _ = get_verse_sequence(collection, project_dir)
    if sequence:
        # Map position to verse_id
        if verse_position < 1 or verse_position > len(sequence):
            print(f"\n✗ Error: Verse position {verse_position} is out of range", file=sys.stderr)
            print(f"  The sequence in data/verses/{collection}.yaml has {len(sequence)} verses", file=sys.stderr)
            print(f"  Valid positions: 1-{len(sequence)}", file=sys.stderr)
            return None

        # Get verse_id from sequence (1-based position)
        verse_id = sequence[verse_position - 1]
        return verse_id

    # Fallback: scan existing files (old behavior)
    verses_dir = project_dir / "_verses" / collection
    if not verses_dir.exists():
        return None

    # Look for files matching the verse number
    # Patterns: chaupai_05.md, doha_05.md, verse_05.md, verse-05.md, etc.
    patterns = [
        f"*_{verse_position:02d}.md",  # chaupai_05.md, doha_05.md
        f"*{verse_position:02d}.md",   # verse05.md (no separator)
        f"*-{verse_position:02d}.md",  # verse-05.md (dash separator)
    ]

    matches = []
    for pattern in patterns:
        matches.extend(verses_dir.glob(pattern))

    # Remove duplicates
    matches = list(set(matches))

    if len(matches) == 1:
        # Found exactly one match - extract verse_id from filename
        verse_id = matches[0].stem  # Remove .md extension
        return verse_id
    elif len(matches) > 1:
        # Multiple matches - ambiguous
        print(f"\n⚠ Multiple verse files found for verse {verse_position}:")
        for match in matches:
            print(f"  - {match.name}")
        print("\nPlease specify which one using --verse-id")
        return None
    else:
        # No matches - this is a new verse, use default pattern
        return f"verse-{verse_position:02d}"


# ==================== YAML Scene Description Support ====================

def load_scenes_from_yaml(collection: str, project_dir: Path = Path.cwd()) -> Optional[Dict]:
    """
    Load scene descriptions from data/scenes/{collection}.yml

    Args:
        collection: Collection key (e.g., "hanuman-chalisa")
        project_dir: Project directory

    Returns:
        Dictionary with scene data, or None if file not found

    Raises:
        UserFriendlyError: If file format is invalid or migration needed
    """
    scenes_dir = project_dir / "data" / "scenes"
    scenes_file = scenes_dir / f"{collection}.yml"

    # Try .yaml extension as fallback
    if not scenes_file.exists():
        scenes_file = scenes_dir / f"{collection}.yaml"

    if not scenes_file.exists():
        # Check if old Markdown format exists
        old_format_file = project_dir / "docs" / "image-prompts" / f"{collection}.md"
        if old_format_file.exists():
            raise UserFriendlyError(
                f"Scene file not found: {scenes_file}",
                [
                    "⚠️  BREAKING CHANGE: Scene descriptions moved to YAML format",
                    "",
                    f"Old location (no longer supported): {old_format_file}",
                    f"New location (required): {scenes_file}",
                    "",
                    "MIGRATION REQUIRED:",
                    "1. Create data/scenes/ directory",
                    f"2. Convert {old_format_file.name} → {scenes_file.name}",
                    "",
                    "Conversion script:",
                    "https://github.com/sanatan-learnings/hanuman-gpt/blob/main/scripts/convert_scenes_to_yaml.py",
                    "",
                    "Or see example YAML files:",
                    "https://github.com/sanatan-learnings/hanuman-gpt/tree/main/data/scenes"
                ]
            )
        return None

    try:
        with open(scenes_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Validate structure
        if not isinstance(data, dict):
            raise UserFriendlyError(
                f"Invalid scene file format: {scenes_file.name}",
                [
                    "Scene file must be a YAML dictionary",
                    "Expected structure: { _meta: {...}, scenes: {...} }",
                    "See: https://github.com/sanatan-learnings/hanuman-gpt/blob/main/data/scenes/"
                ]
            )

        if 'scenes' not in data:
            raise UserFriendlyError(
                f"Missing 'scenes' section in {scenes_file.name}",
                [
                    "Scene file must have a 'scenes' section with verse descriptions",
                    "Format: scenes:\n  verse-01:\n    title: ...\n    description: ...",
                    "See: https://github.com/sanatan-learnings/hanuman-gpt/blob/main/data/scenes/"
                ]
            )

        return data

    except yaml.YAMLError as e:
        raise UserFriendlyError(
            f"Invalid YAML syntax in {scenes_file.name}",
            [
                f"YAML parse error: {str(e)}",
                "Check indentation and syntax",
                "Use a YAML validator: https://www.yamllint.com/"
            ]
        )
    except Exception as e:
        if DEBUG_MODE:
            raise
        raise UserFriendlyError(
            f"Error reading scene file: {scenes_file.name}",
            [
                f"Error: {str(e)}",
                "Check file permissions and encoding (must be UTF-8)",
                "Use --debug flag to see full error details"
            ]
        )


def get_scene_description(collection: str, verse_id: str, project_dir: Path = Path.cwd()) -> Optional[Dict]:
    """
    Get scene description for a specific verse from YAML file.

    Args:
        collection: Collection key
        verse_id: Verse identifier (e.g., "chaupai-05")
        project_dir: Project directory

    Returns:
        Dictionary with 'title' and 'description' keys, or None if not found
    """
    scenes_data = load_scenes_from_yaml(collection, project_dir)

    if not scenes_data:
        return None

    scenes = scenes_data.get('scenes', {})

    # Try exact match first
    if verse_id in scenes:
        scene = scenes[verse_id]
        if isinstance(scene, dict) and 'description' in scene:
            return {
                'title': scene.get('title', ''),
                'description': scene['description']
            }

    # Try with underscores (backward compatibility)
    verse_id_underscore = verse_id.replace('-', '_')
    if verse_id_underscore in scenes:
        scene = scenes[verse_id_underscore]
        if isinstance(scene, dict) and 'description' in scene:
            return {
                'title': scene.get('title', ''),
                'description': scene['description']
            }

    return None


def generate_scene_description(devanagari_text: str, verse_id: str, collection: str) -> str:
    """
    Generate scene description from Devanagari text using GPT-4.

    Args:
        devanagari_text: The canonical Devanagari verse text
        verse_id: Verse identifier (e.g., chaupai_05, verse_01)
        collection: Collection key for context

    Returns:
        Scene description text
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    prompt = f"""You are an expert in Sanskrit/Hindi spiritual texts and visual storytelling. Given this verse from {collection}:

Devanagari: {devanagari_text}

Create a detailed scene description for generating an image with DALL-E 3. The description should:

1. Describe the key visual elements, characters, and setting
2. Specify the mood, atmosphere, and lighting
3. Include important symbolic elements if relevant
4. Be specific about composition and focus
5. Be 2-4 sentences, rich in visual detail but concise

Provide ONLY the scene description, no additional text."""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in spiritual texts and visual storytelling, creating vivid scene descriptions for image generation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7  # Slightly higher for creative descriptions
        )

        scene_description = response.choices[0].message.content.strip()
        return scene_description

    except Exception as e:
        print(f"  ✗ Error generating scene description: {e}", file=sys.stderr)
        return None


def validate_scene_description_exists(collection: str, verse_id: str, project_dir: Path = Path.cwd()) -> bool:
    """
    Check if a scene description exists for the verse in data/scenes/{collection}.yml

    Args:
        collection: Collection key
        verse_id: Verse identifier
        project_dir: Project directory

    Returns:
        True if scene description exists, False otherwise
    """
    scene = get_scene_description(collection, verse_id, project_dir)
    return scene is not None


def ensure_scene_description_exists(collection: str, verse_position: int, verse_id: str, devanagari_text: str,
                                   title_en: str = None, scene_mode: str = "prefer-existing") -> Tuple[bool, str]:
    """
    Ensure scene description exists for the verse. Creates file and/or adds scene if missing.

    Args:
        collection: Collection key
        verse_position: Verse position in sequence (for ordering, not used in scene header)
        verse_id: Verse identifier (e.g., chaupai-05)
        devanagari_text: Canonical Devanagari text for generating description
        title_en: English title of the verse (optional)
        scene_mode: Scene description mode - "require", "prefer-existing", or "auto-generate"

    Returns:
        Tuple of (success: bool, message: str)
        - "require" mode: Returns (False, error_msg) if scene missing
        - "prefer-existing" mode: Returns (True, "existing"|"generated")
        - "auto-generate" mode: Always generates, returns (True, "generated")
    """
    scenes_dir = Path.cwd() / "data" / "scenes"
    scenes_file = scenes_dir / f"{collection}.yml"

    # Try .yaml extension as fallback
    if not scenes_file.exists():
        scenes_file_yaml = scenes_dir / f"{collection}.yaml"
        if scenes_file_yaml.exists():
            scenes_file = scenes_file_yaml

    # Extract verse type and number from verse_id (e.g., "chaupai" and 5 from "chaupai-05")
    verse_type = verse_id.split('-')[0] if '-' in verse_id else 'verse'
    verse_type_title = verse_type.title()  # Capitalize: Chaupai, Shloka, Doha, etc.
    verse_number = extract_verse_number_from_id(verse_id) or verse_position  # Extract from ID, fallback to position

    # Check if scene description already exists
    scene_exists = validate_scene_description_exists(collection, verse_id, Path.cwd())

    # Handle based on scene mode
    if scene_mode == "require":
        # Strict mode: Require existing scene, fail if missing
        if not scene_exists:
            error_msg = f"Scene description required but not found for {verse_id}"
            instructions = [
                f"Add scene description to: {scenes_file}",
                "Expected format:",
                "  scenes:",
                f"    {verse_id}:",
                "      title: \"Brief Title\"",
                "      description: |",
                "        Visual scene description...",
                "",
                "Or use --prefer-existing-scene to auto-generate missing scenes"
            ]
            return False, "\n".join([error_msg] + [f"  → {inst}" for inst in instructions])
        else:
            print(f"  ✓ Using existing scene description for {verse_type_title} {verse_number}")
            return True, "existing"

    elif scene_mode == "prefer-existing":
        # Smart default: Use existing if found, generate if missing
        if scene_exists:
            print(f"  ✓ Using existing scene description for {verse_type_title} {verse_number}")
            return True, "existing"
        else:
            print("  → Existing scene not found, generating with AI...")
            # Fall through to generation logic below
            pass

    elif scene_mode == "auto-generate":
        # Always generate: Ignore existing
        print("  → Generating scene description with AI (auto-generate mode)...")
        # Fall through to generation logic below
        pass

    # Generation logic (for prefer-existing when missing, or auto-generate)
    scenes_dir.mkdir(parents=True, exist_ok=True)

    # Generate new scene description
    print(f"  → Generating scene description for {verse_type_title} {verse_number}...")
    scene_description = generate_scene_description(devanagari_text, verse_id, collection)

    if not scene_description:
        print("  ✗ Failed to generate scene description")
        return False, "generation_failed"

    # Load existing scenes or create new structure
    if scenes_file.exists():
        with open(scenes_file, 'r', encoding='utf-8') as f:
            scenes_data = yaml.safe_load(f) or {}
    else:
        print(f"  → Creating scene descriptions file: {scenes_file.name}")
        scenes_data = {
            '_meta': {
                'collection': collection,
                'description': 'Scene descriptions for image generation',
                'format': 'theme-agnostic scene descriptions'
            },
            'scenes': {}
        }

    # Ensure scenes section exists
    if 'scenes' not in scenes_data:
        scenes_data['scenes'] = {}

    # Build scene entry
    scene_title = title_en if title_en else f"{verse_type_title} {verse_number}"

    # Add/update scene with AI-generated marker in title
    scenes_data['scenes'][verse_id] = {
        'title': f"{scene_title} [AI-Generated - Review Recommended]",
        'description': scene_description
    }

    # Write back to file with nice formatting
    try:
        with open(scenes_file, 'w', encoding='utf-8') as f:
            # Use custom YAML formatting for better readability
            yaml.dump(scenes_data, f,
                     default_flow_style=False,
                     allow_unicode=True,
                     sort_keys=False,
                     width=120)

        if scene_exists:
            print(f"  ✓ Updated scene description for {verse_type_title} {verse_number} in {scenes_file.name}")
        else:
            print(f"  ✓ Added scene description for {verse_type_title} {verse_number} to {scenes_file.name}")

        print("  ⚠ [AI-Generated - Review Recommended]")
        return True, "generated"

    except Exception as e:
        print(f"  ✗ Failed to write scene file: {e}")
        if DEBUG_MODE:
            import traceback
            traceback.print_exc()
        return False, "write_failed"


def generate_image(collection: str, verse: int, theme: str, verse_id: str = None) -> bool:
    """Generate image for the specified verse."""
    print(f"\n{'='*60}")
    print("GENERATING IMAGE")
    print(f"{'='*60}\n")

    # Prompts file will be created if needed by ensure_scene_description_exists
    prompts_file = Path.cwd() / "docs" / "image-prompts" / f"{collection}.md"

    # Use provided verse_id or default to verse-{N:02d}
    if not verse_id:
        verse_id = f"verse-{verse:02d}"

    print(f"✓ Collection: {collection}")
    print(f"✓ Verse: {verse_id}")
    print(f"✓ Theme: {theme}")

    # Run verse-images command
    verse_images_cmd = find_command("verse-images")
    cmd = [
        verse_images_cmd,
        "--collection", collection,
        "--theme", theme,
        "--verse", verse_id
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, check=True)
        print("\n✓ Image generated successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error generating image: {e}")
        return False


def generate_audio(collection: str, verse: int, verse_id: str = None) -> bool:
    """Generate audio for the specified verse."""
    print(f"\n{'='*60}")
    print("GENERATING AUDIO")
    print(f"{'='*60}\n")

    # Use provided verse_id or default to verse-{N:02d}
    if not verse_id:
        verse_id = f"verse-{verse:02d}"

    # Check if verse file exists
    verses_dir = Path.cwd() / "_verses" / collection
    verse_file = verses_dir / f"{verse_id}.md"

    if not verse_file.exists():
        print(f"✗ Error: Verse file not found: {verse_file}")
        print("Please create the verse markdown file first")
        return False

    print(f"✓ Collection: {collection}")
    print(f"✓ Verse: {verse_id}")

    # Run verse-audio command
    verse_audio_cmd = find_command("verse-audio")
    cmd = [
        verse_audio_cmd,
        "--collection", collection,
        "--verse", verse_id
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, check=True)

        # Verify that audio files were actually created with non-zero size
        audio_dir = Path.cwd() / "audio" / collection
        full_audio = audio_dir / f"{verse_id}-full.mp3"
        slow_audio = audio_dir / f"{verse_id}-slow.mp3"

        # Check if files exist
        if not full_audio.exists() or not slow_audio.exists():
            print("\n✗ Audio generation reported success but files not found:")
            if not full_audio.exists():
                print(f"  Missing: {full_audio}")
            if not slow_audio.exists():
                print(f"  Missing: {slow_audio}")
            print("\nThis may indicate an issue with the audio generation workflow.")
            return False

        # Check if files have non-zero size (not corrupted/empty)
        full_size = full_audio.stat().st_size
        slow_size = slow_audio.stat().st_size

        if full_size == 0 or slow_size == 0:
            print("\n✗ Audio generation created corrupted files (0 bytes):")
            if full_size == 0:
                print(f"  Corrupted: {full_audio.name} (0 bytes)")
            if slow_size == 0:
                print(f"  Corrupted: {slow_audio.name} (0 bytes)")
            print("\nPossible causes:")
            print("  - ElevenLabs API returned empty response")
            print("  - Network interruption during download")
            print("  - Insufficient disk space")
            print("\nTry regenerating with: verse-audio --collection {collection} --verse {verse_id} --force")
            return False

        print("\n✓ Audio generated successfully")
        print(f"  ✓ {full_audio.name}")
        print(f"  ✓ {slow_audio.name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error generating audio: {e}")
        return False


def fetch_verse_text(collection: str, verse_id: str) -> Optional[dict]:
    """Fetch traditional Devanagari text for the verse."""
    print(f"\n{'='*60}")
    print("FETCHING VERSE TEXT")
    print(f"{'='*60}\n")

    print(f"✓ Collection: {collection}")
    print(f"✓ Verse ID: {verse_id}")

    # Run verse-fetch-text command
    verse_fetch_cmd = find_command("verse-fetch-text")
    cmd = [
        verse_fetch_cmd,
        "--collection", collection,
        "--verse", verse_id,
        "--format", "json"
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Verse text fetched successfully")

        # Parse and return the JSON result
        data = json.loads(result.stdout)
        if data.get('success'):
            print("\nDevanagari text:")
            print(f"  {data.get('devanagari', 'N/A')}\n")
            return data
        else:
            print(f"✗ Fetch failed: {data.get('error', 'Unknown error')}")
            return None
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error fetching verse text: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"\n✗ Error parsing response: {e}")
        return None


def update_embeddings(collection: str) -> bool:
    """Update vector embeddings for the collection."""
    print(f"\n{'='*60}")
    print("UPDATING EMBEDDINGS")
    print(f"{'='*60}\n")

    print(f"✓ Collection: {collection}")

    # Check if collections.yml exists
    collections_file = Path.cwd() / "_data" / "collections.yml"
    if not collections_file.exists():
        print(f"✗ Error: collections.yml not found at {collections_file}")
        return False

    # Run verse-embeddings command
    verse_embeddings_cmd = find_command("verse-embeddings")

    cmd = [
        verse_embeddings_cmd,
        "--collection", collection,
        "--collections-file", str(collections_file),
        "--verses-dir", "_verses",
        "--output-dir", "data/embeddings/collections"
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, check=True)
        print("\n✓ Embeddings updated successfully")
        print("✓ Output: data/embeddings/collections")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error updating embeddings: {e}")
        return False


def show_directory_structure():
    """Display expected directory structure and conventions."""
    print()
    print("=" * 70)
    print("📁 Expected Directory Structure & Conventions")
    print("=" * 70)
    print()
    print("Your project should follow this structure:")
    print()
    print("""your-project/
├── .env                                  # API keys (gitignored)
├── .env.example                          # Template for API keys
├── _data/
│   └── collections.yml                   # Collection registry
├── _verses/
│   └── <collection-key>/                 # Verse markdown files
│       ├── verse-01.md                   # Dash-separated (recommended)
│       └── chaupai-05.md                 # Custom verse types
├── data/
│   ├── themes/
│   │   └── <collection-key>/             # Theme configurations
│   │       ├── modern-minimalist.yml
│   │       └── kids-friendly.yml
│   └── verses/
│       └── <collection>.yaml             # Canonical verse text (YAML)
├── docs/
│   └── image-prompts/                    # Scene descriptions (auto-generated)
│       └── <collection-key>.md
├── images/                               # Generated images (gitignored)
│   └── <collection-key>/
│       └── <theme-name>/
│           └── verse-01.png
└── audio/                                # Generated audio (gitignored)
    └── <collection-key>/
        ├── verse-01-full.mp3
        └── verse-01-slow.mp3
""")
    print()
    print("📋 Key Conventions:")
    print("-" * 70)
    print("  1. Collection Keys: Use kebab-case (e.g., hanuman-chalisa)")
    print("  2. Verse Files: Use dash-separated format (verse-01.md)")
    print("     • Legacy underscore format (verse_01.md) still supported")
    print("  3. Theme Location: data/themes/{collection}/{theme}.yml")
    print("  4. Canonical Text: data/verses/{collection}.yaml")
    print("  5. Collections Registry: _data/collections.yml with enabled: true")
    print()
    print("🚀 Quick Setup:")
    print("-" * 70)
    print("  # Initialize new project")
    print("  verse-init --project-name my-project")
    print()
    print("  # Validate existing project")
    print("  verse-validate")
    print()
    print("  # Auto-fix common issues")
    print("  verse-validate --fix")
    print()
    print("📚 Documentation:")
    print("-" * 70)
    print("  • Usage Guide: https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/usage.md")
    print("  • Troubleshooting: https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/troubleshooting.md")
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate images and audio for a specific verse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default workflow - generate image + audio (no embeddings)
  verse-generate --collection hanuman-chalisa --verse 15

  # With custom theme
  verse-generate --collection hanuman-chalisa --verse 15 --theme kids-friendly

  # Generate image + audio + embeddings
  verse-generate --collection hanuman-chalisa --verse 15 --embeddings

  # Generate only image
  verse-generate --collection sundar-kaand --verse 3 --image

  # Generate only audio
  verse-generate --collection sankat-mochan-hanumanashtak --verse 5 --audio

  # Generate image + audio (explicit, same as default)
  verse-generate --collection sundar-kaand --verse 3 --image --audio

  # Auto-generate next verse after the last generated verse
  verse-generate --collection sundar-kaand --next

  # Regenerate AI content only (no multimedia)
  verse-generate --collection sundar-kaand --verse 3 --regenerate-content

  # Regenerate content + image
  verse-generate --collection sundar-kaand --verse 3 --regenerate-content --image

  # Regenerate content + image + audio
  verse-generate --collection sundar-kaand --verse 3 --regenerate-content --image --audio

  # Regenerate content + all multimedia
  verse-generate --collection sundar-kaand --verse 3 --regenerate-content --image --audio --embeddings

  # Override auto-detected verse ID (only needed when not using sequence)
  verse-generate --collection sundar-kaand --verse 5 --verse-id chaupai-05

  # List available collections
  verse-generate --list-collections

Note:
  - The --verse flag refers to POSITION in the sequence (from data/verses/{collection}.yaml)
  - Position 1 = first verse in sequence, position 15 = 15th verse in sequence, etc.
  - If data file has sequence, verse ID is mapped from sequence (e.g., position 15 → chaupai-11)
  - If no sequence exists, falls back to old behavior (scanning existing files)
  - Use --next to auto-generate the next verse in the sequence
  - Default behavior: generates image + audio (no embeddings)
  - Use --embeddings to also update vector embeddings (or run verse-embeddings separately)
  - Use --regenerate-content ALONE to only regenerate text (no multimedia)
  - Add --image, --audio, or --embeddings to include specific media
  - Flags can be combined: --image --audio --embeddings
  - Theme defaults to "modern-minimalist" (use --theme to change)

Environment Variables:
  OPENAI_API_KEY      - Required for image generation and embeddings
  ELEVENLABS_API_KEY  - Required for audio generation

✅ Success Criteria Checklist:
  Before running verse-generate, ensure you have:
  □ _data/collections.yml with collection defined and enabled: true
  □ data/verses/{collection}.yml with canonical Devanagari text for verse
  □ _verses/{collection}/ directory exists
  □ OPENAI_API_KEY set (for image/content/embeddings)
  □ ELEVENLABS_API_KEY set (for audio)
  □ data/themes/{collection}/{theme}.yml exists (if using custom theme)

🔧 Error Troubleshooting:
  "Collection not found"
    → Move data/collections.yaml to _data/collections.yml
    → Check collection has enabled: true

  "Verse not found in data file"
    → Add verse to data/verses/{collection}.yml with devanagari field

  "Scene description not found" (warning only)
    → Use --auto-generate-scene to generate scenes automatically
    → Or manually add to data/scenes/{collection}.yml

  "OPENAI_API_KEY not set"
    → Export key: export OPENAI_API_KEY='sk-...'
    → Or create .env file with OPENAI_API_KEY=sk-...

  "Audio generation failed"
    → Check ELEVENLABS_API_KEY is set
    → Verify verse file exists in _verses/{collection}/{verse-id}.md

📊 Batch Processing Examples:
  # Generate verses 1-10 (everything by default)
  verse-generate --collection sundar-kaand --verse 1-10

  # Generate verses 15-20 without embeddings (faster)
  verse-generate --collection sundar-kaand --verse 15-20 --image --audio

  # Regenerate content for verses 1-5 (no multimedia)
  verse-generate --collection sundar-kaand --verse 1-5 --regenerate-content

  # Generate all remaining verses starting from position 21
  for i in {21..50}; do
    verse-generate --collection sundar-kaand --verse $i || break
  done

  # Generate next verse in sequence (auto-detect)
  verse-generate --collection sundar-kaand --next

💰 Cost Estimates (per verse):
  Content Generation (GPT-4):
    ~500-1000 tokens input × $0.03/1K = $0.015-$0.03
    ~1000-2000 tokens output × $0.06/1K = $0.06-$0.12
    Total: ~$0.08-$0.15 per verse

  Image Generation (DALL-E 3):
    Standard 1024x1792: $0.040 per image
    HD 1024x1792: $0.080 per image

  Audio Generation (ElevenLabs):
    ~100-200 characters × 2 speeds = 200-400 chars
    ~$0.30/1K characters = $0.06-$0.12 per verse

  Embeddings (OpenAI):
    ~500 tokens × $0.0001/1K = $0.00005 (negligible)

  Complete Workflow (1 verse):
    Content + Image + Audio + Embeddings
    = $0.08 + $0.04 + $0.09 + $0.00
    ≈ $0.21 per verse (standard quality)

  Batch Example (50 verses):
    50 verses × $0.21 = ~$10.50
    (Image HD: +$2.00, total ~$12.50)
        """
    )

    # List collections
    parser.add_argument(
        "--list-collections",
        action="store_true",
        help="List available collections and exit"
    )

    # Show structure
    parser.add_argument(
        "--show-structure",
        action="store_true",
        help="Show expected directory structure and conventions"
    )

    # Collection and verse identification
    parser.add_argument(
        "--collection",
        type=str,
        help="Collection key (e.g., hanuman-chalisa, sundar-kaand)",
        metavar="KEY"
    )
    parser.add_argument(
        "--verse",
        type=str,
        help="Verse position in sequence or range (e.g., 5, 1-10, 5-20). Position is mapped to verse ID from data/verses/{collection}.yaml sequence.",
        metavar="N or M-N"
    )
    parser.add_argument(
        "--next",
        action="store_true",
        help="Auto-detect and generate the next verse after the last generated verse"
    )

    # Content types (can be combined)
    parser.add_argument(
        "--image",
        action="store_true",
        help="Generate image with DALL-E 3"
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="Generate audio pronunciation with ElevenLabs"
    )
    parser.add_argument(
        "--embeddings",
        dest="update_embeddings",
        action="store_true",
        help="Update vector embeddings for semantic search"
    )
    parser.add_argument(
        "--puranic-context",
        action="store_true",
        help="Generate Puranic context box for the verse"
    )

    # Legacy flag support
    parser.add_argument(
        "--update-embeddings",
        dest="update_embeddings",
        action="store_true",
        help=argparse.SUPPRESS  # Hidden, use --embeddings instead
    )
    parser.add_argument(
        "--no-update-embeddings",
        dest="update_embeddings",
        action="store_false",
        help=argparse.SUPPRESS  # Hidden, not needed with new design
    )

    # Content regeneration
    parser.add_argument(
        "--regenerate-content",
        action="store_true",
        help="Regenerate AI content (transliteration, meaning, translation, story) from canonical Devanagari text"
    )

    # Theme for image generation
    parser.add_argument(
        "--theme",
        default="modern-minimalist",
        help="Theme name for image generation (default: modern-minimalist)",
        metavar="NAME"
    )

    # Verse ID override (for non-numeric verse identifiers)
    parser.add_argument(
        "--verse-id",
        type=str,
        help="Override verse identifier (e.g., chaupai-05, doha-01). If not specified, auto-detects from existing files or defaults to verse-{N:02d}",
        metavar="ID"
    )

    # Scene description mode (mutually exclusive)
    scene_mode_group = parser.add_mutually_exclusive_group()
    scene_mode_group.add_argument(
        "--require-scene",
        action="store_const",
        const="require",
        dest="scene_mode",
        help="Require existing scene description. Exit with error if scene is missing (strict mode for curated projects)"
    )
    scene_mode_group.add_argument(
        "--prefer-existing-scene",
        action="store_const",
        const="prefer-existing",
        dest="scene_mode",
        help="Use existing scene if found, generate with AI if missing (smart default, respects curation)"
    )
    scene_mode_group.add_argument(
        "--auto-generate-scene",
        action="store_const",
        const="auto-generate",
        dest="scene_mode",
        help="Always generate scene descriptions with AI (current behavior, quick prototyping)"
    )
    parser.set_defaults(scene_mode="prefer-existing")  # Smart default

    # Dry-run mode
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be generated without actually creating files or making API calls"
    )

    # Debug mode
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show full error tracebacks and debug information"
    )

    args = parser.parse_args()

    # Set global debug mode
    global DEBUG_MODE
    DEBUG_MODE = args.debug

    # Handle list collections
    if args.list_collections:
        list_collections()
        sys.exit(0)

    # Handle show structure
    if args.show_structure:
        show_directory_structure()
        sys.exit(0)

    # Validate required arguments
    if not args.collection:
        print()
        print("✗ Error: No collection specified")
        print()
        print("The --collection flag is required to identify which verse collection to use.")
        print()
        print("Quick Start:")
        print("  1. List available collections:")
        print("     verse-generate --list-collections")
        print()
        print("  2. Generate content for a verse:")
        print("     verse-generate --collection <collection-key> --verse <position>")
        print()
        print("Examples:")
        print("  verse-generate --collection hanuman-chalisa --verse 1")
        print("  verse-generate --collection sundar-kaand --verse 15 --theme kids-friendly")
        print()
        print("Need help setting up a new project?")
        print("  verse-init --project-name my-project --collection hanuman-chalisa")
        print("  verse-validate  # Check your project structure")
        print("  verse-help      # Comprehensive help and workflows")
        print()
        sys.exit(1)

    # Either --verse or --next must be specified (but not both)
    if args.next and args.verse:
        print()
        print("✗ Error: Cannot use both --next and --verse flags together")
        print()
        print("Choose one:")
        print("  --verse <N>  : Generate a specific verse by position (e.g., --verse 15)")
        print("  --next       : Auto-detect and generate the next verse in sequence")
        print()
        print("Examples:")
        print(f"  verse-generate --collection {args.collection} --verse 15")
        print(f"  verse-generate --collection {args.collection} --next")
        print()
        sys.exit(1)

    if not args.verse and not args.next:
        print()
        print("✗ Error: No verse specified")
        print()
        print("You must specify which verse to generate:")
        print("  --verse <N>  : Generate verse at position N in the sequence")
        print("  --next       : Auto-detect and generate the next verse")
        print()
        print("Examples:")
        print(f"  verse-generate --collection {args.collection} --verse 1")
        print(f"  verse-generate --collection {args.collection} --verse 10-20  # Range")
        print(f"  verse-generate --collection {args.collection} --next")
        print()
        print("Available options:")
        print("  (no flags) : Generate image + audio (default, no embeddings)")
        print("  --image    : Generate image")
        print("  --audio    : Generate audio")
        print("  --embeddings : Update vector embeddings")
        print("  --regenerate-content : Regenerate AI text content")
        print("  --theme <name> : Use a specific theme (default: modern-minimalist)")
        print()
        print("Flags can be combined:")
        print("  --image --audio              : Generate image and audio")
        print("  --regenerate-content --image : Regenerate text + image")
        print()
        print("For more help:")
        print("  verse-help")
        print()
        sys.exit(1)

    # Determine what to generate
    # New simpler design:
    # - No flags = generate image + audio (embeddings opt-in via --embeddings)
    # - --regenerate-content alone = regenerate text only
    # - --regenerate-content + media flags = regenerate text + specified media
    # - Media flags alone = generate specified media only

    has_media_flags = any([args.image, args.audio, args.update_embeddings, args.puranic_context])

    if not has_media_flags and not args.regenerate_content:
        # No flags specified: default to image + audio (embeddings are opt-in via --embeddings)
        generate_image_flag = True
        generate_audio_flag = True
        update_embeddings_flag = False
    else:
        # Use explicit flags
        generate_image_flag = args.image
        generate_audio_flag = args.audio
        update_embeddings_flag = args.update_embeddings

    puranic_context_flag = args.puranic_context
    regenerate_content_flag = args.regenerate_content

    # Validate collection
    if not validate_collection(args.collection):
        sys.exit(1)

    # Handle --next by finding the next verse to generate
    if args.next:
        next_verse = find_next_verse(args.collection)
        if next_verse is None:
            print(f"✗ Error: Could not determine next verse for collection '{args.collection}'")
            sys.exit(1)
        args.verse = str(next_verse)
        print(f"✓ Auto-detected next verse: {next_verse}")

    # Parse verse argument (supports single number or range)
    verse_numbers = []
    if '-' in args.verse:
        # Range format: M-N
        try:
            start, end = args.verse.split('-')
            start_num = int(start.strip())
            end_num = int(end.strip())
            if start_num > end_num:
                print(f"✗ Error: Invalid range {args.verse} (start must be <= end)")
                sys.exit(1)
            verse_numbers = list(range(start_num, end_num + 1))
        except ValueError:
            print(f"✗ Error: Invalid verse range format: {args.verse}")
            print("Use format: M-N (e.g., 1-10, 5-20)")
            sys.exit(1)
    else:
        # Single verse number
        try:
            verse_numbers = [int(args.verse)]
        except ValueError:
            print(f"✗ Error: Invalid verse position: {args.verse}")
            print("")
            print("The --verse flag expects a POSITION NUMBER (e.g., 15), not a verse ID.")
            print("Position refers to the verse's location in the sequence (1st, 2nd, 3rd, etc.)")
            print("")
            print("Examples:")
            print(f"  verse-generate --collection {args.collection} --verse 15    # Generate 15th verse in sequence")
            print(f"  verse-generate --collection {args.collection} --verse 1     # Generate 1st verse in sequence")
            print(f"  verse-generate --collection {args.collection} --next        # Auto-generate next verse")
            print("")
            print("If you need to specify a verse ID directly, use --verse-id:")
            print(f"  verse-generate --collection {args.collection} --verse-id {args.verse}")
            sys.exit(1)

    # Validate verse_id is not used with ranges
    if len(verse_numbers) > 1 and args.verse_id:
        print("✗ Error: Cannot use --verse-id with verse ranges")
        print("The verse ID is auto-detected for each verse in the range")
        sys.exit(1)

    # Display header
    print("\n" + "="*60)
    print("VERSE CONTENT GENERATOR")
    print("="*60)

    print(f"\nCollection: {args.collection}")
    if len(verse_numbers) == 1:
        print(f"Position: {verse_numbers[0]}")
    else:
        print(f"Positions: {verse_numbers[0]}-{verse_numbers[-1]} ({len(verse_numbers)} verses)")
    if generate_image_flag:
        print(f"Theme: {args.theme}")

    print("\nOperations:")
    if regenerate_content_flag:
        print("  ✓ Regenerate AI content (transliteration, meaning, translation, story)")
    if generate_image_flag:
        print("  ✓ Generate image")
    if generate_audio_flag:
        print("  ✓ Generate audio")
    if update_embeddings_flag:
        print("  ✓ Update embeddings")
    if puranic_context_flag:
        print("  ✓ Generate Puranic context")

    if args.dry_run:
        print("\n⚠ DRY-RUN MODE: No files will be created or API calls made")

    print()

    # Pre-generation validation for all verses
    print("="*60)
    print("PRE-GENERATION VALIDATION")
    print("="*60)
    print()

    validation_failed = False
    for idx, verse_position in enumerate(verse_numbers, 1):
        # Determine verse ID first
        if args.verse_id:
            verse_id = args.verse_id
        else:
            verse_id = infer_verse_id(args.collection, verse_position)
            if verse_id is None:
                print(f"✗ Position {verse_position}: Cannot determine verse ID")
                validation_failed = True
                continue

        print(f"Validating position {verse_position} ({verse_id})...")

        # Run comprehensive validation
        is_valid, errors = validate_generation_requirements(
            args.collection,
            verse_id,
            generate_image_flag,
            generate_audio_flag,
            regenerate_content_flag,
            update_embeddings_flag,
            Path.cwd()
        )

        if not is_valid:
            print(f"✗ Validation failed for {verse_id}:")
            for error in errors:
                print(f"  - {error}")
            validation_failed = True
        else:
            print(f"✓ Validation passed for {verse_id}")

    print()

    if validation_failed:
        print("="*60)
        print("✗ VALIDATION FAILED - Cannot proceed with generation")
        print("="*60)
        print("\nPlease fix the errors above and try again.")
        sys.exit(1)

    print("="*60)
    print("✓ ALL VALIDATIONS PASSED - Starting generation")
    print("="*60)
    print()

    # Track overall success across all verses
    overall_results = []

    # Initialize cost tracker
    cost_tracker = CostTracker()

    # Initialize progress bar for batch operations
    progress_bar = None
    if len(verse_numbers) > 1:
        print("\nProcessing verses:")
        # Count total steps: for each verse, we might do content + image + audio + embeddings
        # But we'll just show verse-level progress for simplicity
        progress_bar = ProgressBar(total=len(verse_numbers), width=20)

    # Process each verse in the range
    try:
        for idx, verse_position in enumerate(verse_numbers, 1):
            # Update progress bar
            if progress_bar:
                verse_id_preview = f"verse {idx}/{len(verse_numbers)}"
                progress_bar.update(idx - 1, f"Processing {verse_id_preview}...")
                print()  # New line after progress bar

            # Show progress for batch operations
            if len(verse_numbers) > 1:
                print(f"\n{'#'*60}")
                print(f"# Processing verse {idx}/{len(verse_numbers)}: Position {verse_position}")
                print(f"{'#'*60}\n")

            # Determine verse ID (with smart inference)
            if args.verse_id:
                # User explicitly specified verse ID (only for single verse)
                verse_id = args.verse_id
            else:
                # Try to infer verse ID from position (using sequence or fallback)
                inferred = infer_verse_id(args.collection, verse_position)
                if inferred is None:
                    # Inference failed (out of range or ambiguous)
                    print(f"⚠ Skipping position {verse_position} (cannot determine verse ID)")
                    overall_results.append({
                        'position': verse_position,
                        'success': False,
                        'reason': 'Cannot determine verse ID'
                    })
                    continue
                verse_id = inferred

                # Show inference result
                if len(verse_numbers) == 1:
                    print(f"\n✓ Position {verse_position} → Verse ID: {verse_id}")
                    print("  (To override, use --verse-id)\n")

            # Track success for this verse
            results = {
                'position': verse_position,
                'verse_id': verse_id,
                'verse_file_created': None,
                'regenerate_content': None,
                'image': None,
                'audio': None,
                'embeddings': None,
                'content_cost': 0.0,
                'image_cost': 0.0,
                'audio_cost': 0.0,
                'embeddings_cost': 0.0,
                'verse_file_path': None,
                'verse_file_size': 0,
                'image_file_path': None,
                'image_file_size': 0,
                'audio_files': [],
                'prev_verse': None,
                'next_verse': None
            }

            # Check if verse file exists, create if needed
            verse_file = Path.cwd() / "_verses" / args.collection / f"{verse_id}.md"
            verse_file_existed = verse_file.exists()

            # Step 0: Create verse file if it doesn't exist (required for audio generation)
            if not verse_file_existed:
                print(f"\n{'='*60}")
                print("CREATING VERSE FILE")
                print(f"{'='*60}\n")
                print("  → Verse file not found, creating from canonical source...")

                from verse_sdk.fetch.fetch_verse_text import fetch_from_local_file

                canonical_data = fetch_from_local_file(args.collection, verse_id)
                if not canonical_data or not canonical_data.get('devanagari'):
                    print(f"  ✗ Error: No canonical Devanagari text found for {verse_id}", file=sys.stderr)
                    print(f"  Please create data/verses/{args.collection}.yaml with canonical text", file=sys.stderr)
                    results['verse_file_created'] = False
                else:
                    # Generate content from canonical text
                    generated_content, content_cost = generate_verse_content(
                        canonical_data['devanagari'],
                        args.collection,
                        verse_id,
                        dry_run=args.dry_run,
                        cost_tracker=cost_tracker
                    )
                    results['content_cost'] = content_cost

                    # Create verse markdown file
                    results['verse_file_created'] = create_verse_file_with_content(
                        verse_file,
                        generated_content,
                        args.collection,
                        verse_position,
                        verse_id,
                        Path.cwd()  # Pass current directory as project_dir
                    )

                    if results['verse_file_created']:
                        print("  ✓ Verse file created successfully")
                        # Update previous verse's next_verse field
                        update_previous_verse_navigation(args.collection, verse_id, Path.cwd())
                    else:
                        print("  ✗ Failed to create verse file")

            # Generate content in order: regenerate content → image → audio → embeddings
            # Step 1: Regenerate AI content (optional, only for existing files)
            if regenerate_content_flag and verse_file_existed:
                # Load canonical Devanagari from data/verses/{collection}.yaml
                from verse_sdk.fetch.fetch_verse_text import fetch_from_local_file

                canonical_data = fetch_from_local_file(args.collection, verse_id)
                if not canonical_data or not canonical_data.get('devanagari'):
                    print(f"  ✗ Error: No canonical Devanagari text found for {verse_id}", file=sys.stderr)
                    print(f"  Please create data/verses/{args.collection}.yaml with canonical text", file=sys.stderr)
                    results['regenerate_content'] = False
                else:
                    # Generate content from canonical text
                    generated_content, content_cost = generate_verse_content(
                        canonical_data['devanagari'],
                        args.collection,
                        verse_id,
                        dry_run=args.dry_run,
                        cost_tracker=cost_tracker
                    )
                    results['content_cost'] = content_cost

                    # Update verse markdown file
                    verse_file = Path.cwd() / "_verses" / args.collection / f"{verse_id}.md"
                    results['regenerate_content'] = update_verse_file_with_content(verse_file, generated_content)

            # Step 2: Generate image
            if generate_image_flag:
                # Ensure scene description exists before generating image
                from verse_sdk.fetch.fetch_verse_text import fetch_from_local_file

                print(f"\n{'='*60}")
                print("PREPARING SCENE DESCRIPTION")
                print(f"{'='*60}\n")

                canonical_data = fetch_from_local_file(args.collection, verse_id)
                if not canonical_data or not canonical_data.get('devanagari'):
                    print(f"  ✗ Error: No canonical Devanagari text found for {verse_id}", file=sys.stderr)
                    print(f"  Please create data/verses/{args.collection}.yaml with canonical text", file=sys.stderr)
                    print("  Cannot generate scene description without canonical text.", file=sys.stderr)
                    results['image'] = False
                else:
                    # Try to get title from verse file
                    verse_file = Path.cwd() / "_verses" / args.collection / f"{verse_id}.md"
                    title_en = None
                    if verse_file.exists():
                        try:
                            with open(verse_file, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                            if file_content.startswith('---'):
                                parts = file_content.split('---', 2)
                                if len(parts) >= 3:
                                    frontmatter = yaml.safe_load(parts[1])
                                    title_en = frontmatter.get('title_en')
                        except Exception:
                            pass  # If we can't read title, continue without it

                    # Ensure scene description exists (handles all modes: require/prefer-existing/auto-generate)
                    scene_ready, scene_source = ensure_scene_description_exists(
                        args.collection,
                        verse_position,
                        verse_id,
                        canonical_data['devanagari'],
                        title_en,
                        scene_mode=args.scene_mode
                    )

                    if scene_ready:
                        results['image'] = generate_image(args.collection, verse_position, args.theme, verse_id)
                    else:
                        print("  ✗ Failed to prepare scene description", file=sys.stderr)
                        results['image'] = False

            # Step 3: Generate audio
            if generate_audio_flag:
                results['audio'] = generate_audio(args.collection, verse_position, verse_id)

            # Step 4: Generate Puranic context
            if puranic_context_flag:
                from verse_sdk.cli.puranic_context import process_verse as generate_puranic_context_for_verse
                verse_file_path = Path.cwd() / "_verses" / args.collection / f"{verse_id}.md"
                result = generate_puranic_context_for_verse(verse_file_path, regenerate=False)
                results['puranic_context'] = result in ('added', 'regenerated')

            # Step 5: Update embeddings (only once at the end for batch)
            if update_embeddings_flag:
                # For batch operations, only update embeddings after all verses
                if len(verse_numbers) == 1 or idx == len(verse_numbers):
                    results['embeddings'] = update_embeddings(args.collection)
                else:
                    results['embeddings'] = None  # Will update at the end

            # Store results for this verse
            overall_results.append(results)

        # Finish progress bar
        if progress_bar:
            progress_bar.finish("All verses processed")
            print()

    except KeyboardInterrupt:
        print("\n\n⚠ Generation interrupted by user")
        sys.exit(1)
    except UserFriendlyError as e:
        e.display()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}", file=sys.stderr)
        if DEBUG_MODE:
            import traceback
            traceback.print_exc()
        else:
            print("Use --debug flag to see full error details", file=sys.stderr)
        sys.exit(1)

    # Summary
    print(f"\n{'='*60}")
    print("GENERATION SUMMARY")
    print(f"{'='*60}\n")

    if len(overall_results) == 1:
        # Single verse summary
        results = overall_results[0]

        # Operations status
        print("Operations:")
        if results['verse_file_created'] is not None:
            status = "✓" if results['verse_file_created'] else "✗"
            print(f"  {status} Verse file creation: {'Success' if results['verse_file_created'] else 'Failed'}")

        if regenerate_content_flag:
            status = "✓" if results['regenerate_content'] else "✗"
            cost_str = cost_tracker.format_cost(results.get('content_cost', 0))
            print(f"  {status} Regenerate content: {'Success' if results['regenerate_content'] else 'Failed'} ({cost_str})")

        if generate_image_flag:
            status = "✓" if results['image'] else "✗"
            cost_str = cost_tracker.format_cost(results.get('image_cost', 0))
            print(f"  {status} Image: {'Success' if results['image'] else 'Failed'} ({cost_str})")

        if generate_audio_flag:
            status = "✓" if results['audio'] else "✗"
            cost_str = cost_tracker.format_cost(results.get('audio_cost', 0))
            print(f"  {status} Audio: {'Success' if results['audio'] else 'Failed'} ({cost_str})")

        if update_embeddings_flag:
            status = "✓" if results['embeddings'] else "✗"
            cost_str = cost_tracker.format_cost(results.get('embeddings_cost', 0))
            print(f"  {status} Embeddings: {'Success' if results['embeddings'] else 'Failed'} ({cost_str})")

        if puranic_context_flag:
            status = "✓" if results.get('puranic_context') else "✗"
            print(f"  {status} Puranic context: {'Success' if results.get('puranic_context') else 'Failed or skipped'}")

        # File paths and sizes
        print("\nGenerated Files:")
        if results.get('verse_file_path'):
            size_str = format_file_size(results.get('verse_file_size', 0))
            print(f"  📄 Verse: {results['verse_file_path']} ({size_str})")

        if results.get('image_file_path'):
            size_str = format_file_size(results.get('image_file_size', 0))
            print(f"  🖼️  Image: {results['image_file_path']} ({size_str})")

        if results.get('audio_files'):
            for audio_path, audio_size in results['audio_files']:
                size_str = format_file_size(audio_size)
                print(f"  🔊 Audio: {audio_path} ({size_str})")

        # Navigation
        if results.get('prev_verse') or results.get('next_verse'):
            print("\nNavigation:")
            if results.get('prev_verse'):
                print(f"  ← Previous: {results['prev_verse']}")
            if results.get('next_verse'):
                print(f"  → Next: {results['next_verse']}")

        # Total cost
        total_cost = cost_tracker.get_total()
        if total_cost > 0:
            print(f"\nTotal Cost: {cost_tracker.format_cost(total_cost)}")
            print("  Breakdown:")
            for category, cost in cost_tracker.costs.items():
                if cost > 0:
                    print(f"    - {category.replace('_', ' ').title()}: {cost_tracker.format_cost(cost)}")

        print()

        # Exit with appropriate code
        all_results = [r for r in results.values() if isinstance(r, bool)]
        if all_results and all(all_results):
            print("✓ All tasks completed successfully!")
            sys.exit(0)
        elif any(all_results):
            print("⚠ Some tasks completed with errors")
            sys.exit(1)
        else:
            print("✗ All tasks failed")
            sys.exit(1)
    else:
        # Batch summary
        print(f"Total verses processed: {len(overall_results)}")
        print()

        success_count = 0
        failed_verses = []

        for result in overall_results:
            if 'reason' in result:
                # Skipped verse
                failed_verses.append(f"  Verse {result['verse']}: {result['reason']}")
                continue

            # Check if all operations succeeded
            ops = []
            if result['verse_file_created'] is not None:
                ops.append(result['verse_file_created'])
            if regenerate_content_flag and result['regenerate_content'] is not None:
                ops.append(result['regenerate_content'])
            if generate_image_flag and result['image'] is not None:
                ops.append(result['image'])
            if generate_audio_flag and result['audio'] is not None:
                ops.append(result['audio'])

            if ops and all(ops):
                success_count += 1
            else:
                failed_ops = []
                if result['verse_file_created'] is False:
                    failed_ops.append("verse file")
                if regenerate_content_flag and not result['regenerate_content']:
                    failed_ops.append("content")
                if generate_image_flag and not result['image']:
                    failed_ops.append("image")
                if generate_audio_flag and not result['audio']:
                    failed_ops.append("audio")

                failed_verses.append(f"  Verse {result['verse']}: {', '.join(failed_ops)}")

        print(f"✓ Successful: {success_count}/{len(overall_results)}")

        if failed_verses:
            print(f"✗ Failed: {len(failed_verses)}/{len(overall_results)}")
            for fv in failed_verses:
                print(fv)

        if update_embeddings_flag:
            # Report embeddings update (done once at the end)
            last_result = overall_results[-1]
            if last_result.get('embeddings'):
                print("\n✓ Embeddings updated for collection")
            else:
                print("\n✗ Embeddings update failed")

        print()

        if success_count == len(overall_results):
            print("✓ All verses completed successfully!")
            sys.exit(0)
        elif success_count > 0:
            print("⚠ Some verses completed with errors")
            sys.exit(1)
        else:
            print("✗ All verses failed")
            sys.exit(1)


if __name__ == '__main__':
    main()
