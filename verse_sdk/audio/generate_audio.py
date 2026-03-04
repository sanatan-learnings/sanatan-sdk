#!/usr/bin/env python3
"""
Generate audio pronunciations for Hanuman Chalisa verses using Eleven Labs API.

This script:
1. Reads verse files from _verses/ directory
2. Extracts Devanagari text for pronunciation
3. Uses Eleven Labs API to generate audio in two speeds (full and slow)
4. Saves MP3 files to audio/ directory

Usage:
    python scripts/generate_audio.py [--start-from FILENAME] [--voice-id VOICE_ID]

Environment Variables:
    ELEVENLABS_API_KEY - Your Eleven Labs API key (required)

Output:
    audio/doha-01-full.mp3, audio/doha-01-slow.mp3
    audio/doha-02-full.mp3, audio/doha-02-slow.mp3
    audio/verse-01-full.mp3, audio/verse-01-slow.mp3
    ... (86 files total for 43 verses)
"""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from verse_sdk.utils.credentials import has_dotenv_support, resolve_api_key

try:
    from elevenlabs import VoiceSettings
    from elevenlabs.client import ElevenLabs
    from elevenlabs.environment import ElevenLabsEnvironment
except ImportError:
    print("Error: elevenlabs package not installed")
    print("Install with: pip install elevenlabs")
    sys.exit(1)

# Project paths
# Use current working directory (where the user runs the command)
# This allows the SDK to work with any project structure
PROJECT_DIR = Path.cwd()

# Voice settings
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice (female, clear)
FULL_SPEED_STABILITY = 0.5
FULL_SPEED_SIMILARITY = 0.75
SLOW_SPEED_STABILITY = 0.7
SLOW_SPEED_SIMILARITY = 0.8


class AudioGenerator:
    """Generate audio files using Eleven Labs API."""

    def __init__(self, api_key: str, voice_id: str = DEFAULT_VOICE_ID, collection: str = None):
        """
        Initialize the audio generator.

        Args:
            api_key: Eleven Labs API key
            voice_id: Voice ID to use for generation
            collection: Collection key (e.g., 'hanuman-chalisa', 'sundar-kaand')
        """
        # Initialize client with correct environment for data residency
        if "_residency_eu" in api_key:
            # Use EU production environment
            self.client = ElevenLabs(
                api_key=api_key,
                environment=ElevenLabsEnvironment.PRODUCTION_EU
            )
            print("✓ Using EU production environment")
        else:
            # Use default global environment
            self.client = ElevenLabs(api_key=api_key)
            print("✓ Using global production environment")

        self.voice_id = voice_id
        self.collection = collection

        # Set collection-specific directories
        if collection:
            self.verses_dir = PROJECT_DIR / "_verses" / collection
            self.audio_dir = PROJECT_DIR / "audio" / collection
        else:
            self.verses_dir = PROJECT_DIR / "_verses"
            self.audio_dir = PROJECT_DIR / "audio"

        # Create audio directory if it doesn't exist
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def parse_verse_files(self, specific_verse: Optional[str] = None) -> Dict[str, str]:
        """
        Parse all verse files and extract Devanagari text.

        Args:
            specific_verse: Optional verse stem to generate only (e.g., 'verse-01')

        Returns:
            Dictionary mapping filename to Devanagari text
        """
        verses = {}

        if not self.verses_dir.exists():
            print(f"Error: Verses directory not found: {self.verses_dir}")
            return verses

        verse_files = sorted(self.verses_dir.glob("*.md"))

        # Filter to specific verse if requested
        if specific_verse:
            verse_files = [f for f in verse_files if f.stem == specific_verse]
            if not verse_files:
                print(f"Error: Verse '{specific_verse}' not found in {self.verses_dir}")
                return verses

        for verse_file in verse_files:
            content = verse_file.read_text(encoding='utf-8')

            # Extract front matter
            parts = content.split('---')
            if len(parts) < 3:
                continue

            front_matter = parts[1]

            # Extract devanagari text - support multiple YAML formats:
            # 1. devanagari: 'text' (quoted string, possibly multi-line)
            # 2. devanagari: text (plain string)
            # 3. devanagari: | text (YAML literal block)
            devanagari = None

            # Try YAML literal block format first (devanagari: |)
            match = re.search(
                r'devanagari:\s*\|\s*\n(.*?)(?=\n\w+:|---|\Z)',
                front_matter,
                re.DOTALL
            )
            if match:
                devanagari = match.group(1).strip()
            else:
                # Try quoted string format (devanagari: 'text' or devanagari: "text")
                match = re.search(
                    r'devanagari:\s*[\'\"](.*?)[\'\"]',
                    front_matter,
                    re.DOTALL
                )
                if match:
                    devanagari = match.group(1).strip()
                else:
                    # Try plain string format (devanagari: text)
                    match = re.search(
                        r'devanagari:\s*([^\n]+?)(?:\n|$)',
                        front_matter
                    )
                    if match:
                        devanagari = match.group(1).strip()

            if devanagari:

                # Determine base filename (doha_01, verse_01, etc.)
                base_name = verse_file.stem

                verses[base_name] = devanagari
            else:
                # No devanagari field found - warn user
                print(f"  ⚠ Warning: No 'devanagari' field found in {verse_file.name}")
                print("    Expected one of these formats in frontmatter:")
                print("      devanagari: text")
                print("      devanagari: 'text'")
                print("      devanagari: |")
                print("        text")

        print(f"✓ Parsed {len(verses)} verses from {self.verses_dir}")
        return verses

    def generate_audio(
        self,
        text: str,
        output_path: Path,
        speed: str = "full",
        retry_count: int = 3
    ) -> bool:
        """
        Generate audio file using Eleven Labs API.

        Args:
            text: Text to convert to speech
            output_path: Path to save the MP3 file
            speed: "full" or "slow"
            retry_count: Number of retries on failure

        Returns:
            True if successful, False otherwise
        """
        # Voice settings (same for both speeds - actual slowing done via ffmpeg)
        voice_settings = VoiceSettings(
            stability=FULL_SPEED_STABILITY,
            similarity_boost=FULL_SPEED_SIMILARITY,
            style=0.0,
            use_speaker_boost=True
        )

        # Add slight pauses between lines for clarity
        if speed == "slow":
            text = text.replace('\n', ' ... ')

        for attempt in range(1, retry_count + 1):
            try:
                # Generate audio using text_to_speech API
                audio = self.client.text_to_speech.convert(
                    voice_id=self.voice_id,
                    text=text,
                    model_id="eleven_multilingual_v2",  # Supports Hindi
                    voice_settings=voice_settings
                )

                # Ensure parent directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Save to temporary file first
                temp_path = output_path.with_suffix('.temp.mp3') if speed == "slow" else output_path

                # Write audio chunks and track total bytes written
                bytes_written = 0
                with open(temp_path, 'wb') as f:
                    for chunk in audio:
                        f.write(chunk)
                        bytes_written += len(chunk)

                # Verify we received data from the API
                if bytes_written == 0:
                    print("  ✗ Error: ElevenLabs API returned empty audio stream")
                    print("    This may indicate:")
                    print("      - API quota exceeded")
                    print("      - Invalid API key or voice ID")
                    print("      - Text cannot be processed")
                    if temp_path.exists():
                        temp_path.unlink()
                    return False

                # If slow speed, apply audio processing to slow it down
                if speed == "slow":
                    success = self._slow_down_audio(temp_path, output_path)
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()
                    if not success:
                        return False

                # Verify file was written with non-zero size
                if not output_path.exists():
                    print(f"  ✗ Error: Output file was not created: {output_path}")
                    return False

                file_size = output_path.stat().st_size
                if file_size == 0:
                    print(f"  ✗ Error: Generated file is empty (0 bytes): {output_path.name}")
                    print("    This may indicate:")
                    print("      - Empty response from ElevenLabs API")
                    print("      - Network interruption during download")
                    print("      - API quota exceeded")
                    # Delete the empty file
                    output_path.unlink()
                    return False

                return True

            except Exception as e:
                if attempt < retry_count:
                    wait_time = attempt * 5
                    print(f"  Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"✗ Error generating {output_path.name} (attempt {attempt}/{retry_count}): {e}")
                    return False

        return False

    def _slow_down_audio(self, input_path: Path, output_path: Path, speed_factor: float = 0.75) -> bool:
        """
        Slow down audio file without changing pitch using ffmpeg.

        Args:
            input_path: Input audio file
            output_path: Output audio file
            speed_factor: Speed factor (0.75 = 75% speed = slower)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if ffmpeg is available
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                print("  ⚠ ffmpeg not found - slow version will be same as full speed")
                # Just copy the file
                import shutil
                shutil.copy(input_path, output_path)
                return True

            # Use atempo filter to slow down without changing pitch
            # atempo range is 0.5 to 2.0, so we use 0.75 for 25% slower
            cmd = [
                'ffmpeg',
                '-i', str(input_path),
                '-filter:a', f'atempo={speed_factor}',
                '-y',  # Overwrite output file
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0:
                return True
            else:
                print(f"  ⚠ ffmpeg error: {result.stderr.decode()[:100]}")
                # Fallback: just copy the file
                import shutil
                shutil.copy(input_path, output_path)
                return True

        except Exception as e:
            print(f"  ⚠ Error slowing down audio: {e}")
            # Fallback: just copy the file
            import shutil
            shutil.copy(input_path, output_path)
            return True

    def generate_all(self, start_from: Optional[str] = None, only_file: Optional[str] = None, regenerate_files: Optional[list] = None, specific_verse: Optional[str] = None):
        """
        Generate all audio files for all verses.

        Args:
            start_from: Optional filename to resume from (e.g., 'verse-15-full.mp3')
            only_file: Optional single filename to generate (e.g., 'doha-01-full.mp3')
            regenerate_files: Optional list of filenames to regenerate
            specific_verse: Optional verse stem to generate only (e.g., 'verse-01')
        """
        verses = self.parse_verse_files(specific_verse=specific_verse)

        if not verses:
            print(f"Error: No verses found in {self.verses_dir}")
            return

        # Handle --regenerate option: delete specified files
        if regenerate_files:
            print(f"\n🎙️  Preparing to regenerate {len(regenerate_files)} file(s)...\n")
            deleted_count = 0
            for filename in regenerate_files:
                file_path = self.audio_dir / filename
                if file_path.exists():
                    file_path.unlink()
                    print(f"  ✓ Deleted: {filename}")
                    deleted_count += 1
                else:
                    print(f"  ⚠ Not found (will generate): {filename}")

            if deleted_count > 0:
                print(f"\n✓ Deleted {deleted_count} existing file(s).")
            print("→ Will now regenerate missing files...\n")

        total_files = len(verses) * 2  # full and slow for each verse
        generated = 0
        skipped = 0
        failed = 0

        # Determine starting point
        should_skip = start_from is not None

        # Handle --only option: generate just one file
        if only_file:
            print(f"\n🎙️  Generating single file: {only_file}\n")
            total_files = 1
        else:
            print(f"\n🎙️  Starting audio generation for {len(verses)} verses ({total_files} files total)\n")

        for idx, (base_name, devanagari) in enumerate(verses.items(), 1):
            # Generate both full and slow versions
            for speed in ["full", "slow"]:
                filename = f"{base_name}-{speed}.mp3"
                output_path = self.audio_dir / filename

                # If --only is specified, skip files that don't match
                if only_file and filename != only_file:
                    continue

                # Check if we should skip (for resume functionality)
                if should_skip:
                    if filename == start_from:
                        should_skip = False
                        print(f"→ Resuming from {filename}")
                    else:
                        skipped += 1
                        continue

                # Skip if file already exists (unless we're regenerating it)
                if output_path.exists() and not (regenerate_files and filename in regenerate_files):
                    if not only_file:  # Don't show skip message if using --only
                        print(f"[{generated + failed + skipped + 1}/{total_files}] ⊙ Skipping {filename} (already exists)")
                    skipped += 1
                    continue

                print(f"[{generated + failed + skipped + 1}/{total_files}] → Generating {filename}...")
                print(f"  Text: {devanagari[:50]}...")

                success = self.generate_audio(
                    text=devanagari,
                    output_path=output_path,
                    speed=speed
                )

                if success:
                    # Double-check file exists and has content (defensive check)
                    if output_path.exists() and output_path.stat().st_size > 0:
                        file_size = output_path.stat().st_size / 1024  # KB
                        print(f"  ✓ Generated {filename} ({file_size:.1f} KB)")
                        generated += 1
                    else:
                        print(f"  ✗ Failed to generate {filename} (file missing or empty)")
                        failed += 1
                else:
                    print(f"  ✗ Failed to generate {filename}")
                    failed += 1

                # Rate limiting - wait between requests
                time.sleep(1)

        # Summary
        print("\n" + "="*60)
        print("✓ Generation complete!")
        print(f"  Generated: {generated}/{total_files}")
        print(f"  Skipped:   {skipped}/{total_files} (already existed)")
        print(f"  Failed:    {failed}/{total_files}")
        print(f"\nAudio files saved to: {self.audio_dir}")

        if failed > 0:
            print(f"\n⚠ {failed} files failed to generate. You can regenerate them by deleting and running again.")


def validate_collection(collection: str, project_dir: Path = PROJECT_DIR) -> bool:
    """Validate that collection exists."""
    verses_dir = project_dir / "_verses" / collection
    if not verses_dir.exists():
        print(f"✗ Error: Collection directory not found: {verses_dir}")
        print("\nAvailable collections:")
        list_collections()
        return False

    # Check if there are any verse files
    verse_files = list(verses_dir.glob("*.md"))
    if not verse_files:
        print(f"✗ Error: No verse files found in {verses_dir}")
        return False

    return True


def list_collections(project_dir: Path = PROJECT_DIR):
    """List available collections."""
    verses_base = project_dir / "_verses"
    if not verses_base.exists():
        print("No _verses directory found")
        return

    collections = [d for d in verses_base.iterdir() if d.is_dir()]
    if not collections:
        print("No collections found in _verses/")
        return

    print("\nAvailable collections:")
    for coll_dir in sorted(collections):
        verse_count = len(list(coll_dir.glob("*.md")))
        print(f"  ✓ {coll_dir.name:35s} ({verse_count} verses)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate audio pronunciations for verse collections"
    )
    parser.add_argument(
        "--collection",
        required=False,  # Not required if --list-collections is used
        help="Collection key (e.g., hanuman-chalisa, sundar-kaand, sankat-mochan-hanumanashtak)",
        metavar="KEY"
    )
    parser.add_argument(
        "--verse",
        help="Generate audio for specific verse only (e.g., verse-01, chaupai-03)",
        metavar="VERSE"
    )
    parser.add_argument(
        "--start-from",
        help="Resume from specific file (e.g., verse-15-full.mp3)",
        metavar="FILENAME"
    )
    parser.add_argument(
        "--only",
        help="Generate only one specific file (e.g., doha-01-full.mp3)",
        metavar="FILENAME"
    )
    parser.add_argument(
        "--regenerate",
        help="Regenerate specific files (comma-separated, e.g., doha-01-full.mp3,verse-10-slow.mp3)",
        metavar="FILES"
    )
    parser.add_argument(
        "--voice-id",
        help=f"Eleven Labs voice ID (default: {DEFAULT_VOICE_ID})",
        default=DEFAULT_VOICE_ID,
        metavar="VOICE_ID"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regenerate ALL audio files (deletes all existing MP3s with confirmation)"
    )
    parser.add_argument(
        "--list-collections",
        action="store_true",
        help="List available collections and exit"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="ElevenLabs API key (precedence: --api-key > ELEVENLABS_API_KEY env > .env fallback)",
    )

    args = parser.parse_args()

    # Handle --list-collections
    if args.list_collections:
        list_collections()
        sys.exit(0)

    # Validate required collection parameter
    if not args.collection:
        parser.error("--collection is required")

    # Resolve API key with consistent precedence.
    api_key = resolve_api_key(
        "ELEVENLABS_API_KEY",
        explicit_key=args.api_key,
        project_dir=PROJECT_DIR,
        placeholder_values={"your-api-key-here"},
    )
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not set")
        print("\nSet your API key by either:")
        print("  1. --api-key argument")
        print("  2. export ELEVENLABS_API_KEY='your-key-here'")
        print("  3. Create .env file with: ELEVENLABS_API_KEY=your-key-here")
        if not has_dotenv_support():
            print("\nNote: .env fallback requires python-dotenv.")
            print("Install with: pip install python-dotenv")
        print("\nGet your API key from: https://elevenlabs.io/app/settings/api-keys")
        sys.exit(1)

    # Validate collection
    if not validate_collection(args.collection):
        sys.exit(1)

    # Check for conflicting options
    if args.force and args.regenerate:
        print("Error: Cannot use --force and --regenerate together")
        print("Use --force to regenerate ALL files, or --regenerate for specific files")
        sys.exit(1)

    if args.force and args.only:
        print("Error: Cannot use --force and --only together")
        print("Use --force to regenerate ALL files, or --only for a single file")
        sys.exit(1)

    # Handle --force option
    if args.force:
        audio_dir = PROJECT_DIR / "audio" / args.collection
        if audio_dir.exists():
            audio_files = list(audio_dir.glob("*.mp3"))
            if audio_files:
                print(f"\n⚠️  WARNING: Force regeneration will delete {len(audio_files)} existing audio files!")
                print(f"Directory: {audio_dir}")
                print()
                response = input(f"Are you sure you want to delete and regenerate ALL audio files for '{args.collection}'? (y/n): ")

                if response.lower() in ['y', 'yes']:
                    print()
                    print("Deleting existing audio files...")
                    for f in audio_files:
                        f.unlink()
                    print(f"✓ Deleted {len(audio_files)} audio file(s)")
                    print("Will now regenerate all audio files...")
                    print()
                else:
                    print("Aborted. No files were deleted.")
                    sys.exit(0)
            else:
                print("No existing audio files found. Will generate all files.")
                print()
        else:
            print("Audio directory not found. Will create and generate all files.")
            print()

    # Parse regenerate files if provided
    regenerate_files = None
    if args.regenerate:
        regenerate_files = [f.strip() for f in args.regenerate.split(',')]

    # Initialize generator with collection
    generator = AudioGenerator(
        api_key=api_key,
        voice_id=args.voice_id,
        collection=args.collection
    )

    # Generate audio files
    generator.generate_all(
        start_from=args.start_from,
        only_file=args.only,
        regenerate_files=regenerate_files,
        specific_verse=args.verse
    )


if __name__ == "__main__":
    main()
