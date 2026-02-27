#!/usr/bin/env python3
"""
Collection status checker - shows completion status for verse collections.

This command provides a comprehensive overview of what content exists and what's missing:
- Verse files and their metadata
- Audio files (full and slow speed)
- Image files
- Embedding status
- Text validation against normative source
- Completion percentage

Usage:
    # Check specific collection
    verse-status --collection hanuman-chalisa

    # Check all enabled collections
    verse-status --all-collections

    # Validate text against normative source
    verse-status --collection sundar-kaand --validate-text

    # Validate specific verse
    verse-status --collection sundar-kaand --verse chaupai_01 --validate-text

    # Detailed report with file paths
    verse-status --collection sundar-kaand --detailed

    # JSON output for scripting
    verse-status --collection hanuman-chalisa --format json
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    print("Error: python-dotenv package not installed")
    print("Install with: pip install python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()


def get_file_info(file_path: Path) -> Optional[Dict]:
    """Get file metadata if it exists."""
    if not file_path.exists():
        return None

    stat = file_path.stat()
    return {
        'exists': True,
        'size': stat.st_size,
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'path': str(file_path)
    }


def parse_verse_frontmatter(verse_file: Path) -> Dict:
    """Parse YAML frontmatter from verse markdown file."""
    if not verse_file.exists():
        return {}

    try:
        with open(verse_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract frontmatter between --- markers
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                return frontmatter or {}
    except Exception as e:
        print(f"Warning: Could not parse {verse_file}: {e}", file=sys.stderr)

    return {}


def load_normative_verses(collection: str, project_dir: Path) -> Dict:
    """Load normative verses from data/verses/{collection}.yaml or .yml"""
    # Try .yaml first, then .yml
    verses_file = project_dir / "data" / "verses" / f"{collection}.yaml"
    if not verses_file.exists():
        verses_file = project_dir / "data" / "verses" / f"{collection}.yml"

    if not verses_file.exists():
        return {}

    try:
        with open(verses_file, 'r', encoding='utf-8') as f:
            verses_data = yaml.safe_load(f)

        # Filter out metadata keys (starting with _)
        if verses_data:
            return {k: v for k, v in verses_data.items() if not k.startswith('_')}
        return {}
    except Exception as e:
        print(f"Warning: Could not load normative verses from {verses_file}: {e}", file=sys.stderr)
        return {}


def normalize_text(text: str) -> str:
    """Normalize text for comparison (remove extra whitespace, normalize punctuation)."""
    import re
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    # Normalize dandas
    text = text.replace('॥', '।।')
    text = text.replace('।।।', '।।')
    return text


def validate_verse_text(verse_id: str, verse_frontmatter: Dict, normative_verses: Dict) -> Dict:
    """
    Validate verse text against normative source.

    Returns:
        Dict with validation results:
        - status: 'match' | 'minor_diff' | 'mismatch' | 'missing_normative' | 'missing_verse'
        - message: Description of validation result
        - normative_text: Text from normative source
        - current_text: Text from verse file
        - differences: List of differences (if any)
    """
    # Check if normative text exists
    if verse_id not in normative_verses:
        return {
            'status': 'missing_normative',
            'message': 'Not found in normative source',
            'normative_text': None,
            'current_text': verse_frontmatter.get('devanagari'),
            'differences': []
        }

    # Get texts
    normative_data = normative_verses[verse_id]
    normative_text = normative_data.get('devanagari') if isinstance(normative_data, dict) else None
    current_text = verse_frontmatter.get('devanagari')

    if not current_text:
        return {
            'status': 'missing_verse',
            'message': 'Devanagari text missing in verse file',
            'normative_text': normative_text,
            'current_text': None,
            'differences': []
        }

    if not normative_text:
        return {
            'status': 'missing_normative',
            'message': 'Devanagari text missing in normative source',
            'normative_text': None,
            'current_text': current_text,
            'differences': []
        }

    # Normalize both texts for comparison
    norm_normalized = normalize_text(normative_text)
    curr_normalized = normalize_text(current_text)

    # Exact match after normalization
    if norm_normalized == curr_normalized:
        # Check if original texts match (before normalization)
        if normative_text.strip() == current_text.strip():
            return {
                'status': 'match',
                'message': 'Exact match with normative text',
                'normative_text': normative_text,
                'current_text': current_text,
                'differences': []
            }
        else:
            return {
                'status': 'minor_diff',
                'message': 'Minor differences (whitespace/punctuation)',
                'normative_text': normative_text,
                'current_text': current_text,
                'differences': ['Whitespace or punctuation differences']
            }

    # Significant mismatch
    differences = []
    if len(norm_normalized) != len(curr_normalized):
        differences.append(f"Length differs: normative={len(norm_normalized)}, current={len(curr_normalized)}")

    # Find first difference
    for i, (nc, cc) in enumerate(zip(norm_normalized, curr_normalized)):
        if nc != cc:
            context_start = max(0, i - 10)
            context_end = min(len(norm_normalized), i + 10)
            differences.append(f"First diff at pos {i}: ...{norm_normalized[context_start:context_end]}...")
            break

    return {
        'status': 'mismatch',
        'message': 'Text does not match normative source',
        'normative_text': normative_text,
        'current_text': current_text,
        'differences': differences
    }


def check_verse_status(
    collection: str,
    verse_file: Path,
    project_dir: Path,
    normative_verses: Optional[Dict] = None,
    validate_text: bool = False
) -> Dict:
    """Check status of a single verse."""
    verse_id = verse_file.stem  # Remove .md extension

    # Parse frontmatter
    frontmatter = parse_verse_frontmatter(verse_file)

    # Check audio files
    audio_dir = project_dir / "audio" / collection
    audio_full = audio_dir / f"{verse_id}-full.mp3"
    audio_slow = audio_dir / f"{verse_id}-slow.mp3"

    # Check image files (check common themes)
    images_dir = project_dir / "images" / collection
    themes = ['modern-minimalist', 'traditional', 'kids-friendly', 'devotional']
    image_files = {}

    for theme in themes:
        theme_dir = images_dir / theme
        img_file = theme_dir / f"{verse_id}.png"
        if img_file.exists():
            image_files[theme] = get_file_info(img_file)

    # Default theme image
    default_image = images_dir / f"{verse_id}.png"
    if default_image.exists():
        image_files['default'] = get_file_info(default_image)

    result = {
        'verse_id': verse_id,
        'verse_file': get_file_info(verse_file),
        'frontmatter': frontmatter,
        'audio': {
            'full': get_file_info(audio_full),
            'slow': get_file_info(audio_slow)
        },
        'images': image_files,
        'has_devanagari': bool(frontmatter.get('devanagari')),
        'has_transliteration': bool(frontmatter.get('transliteration')),
        'has_meaning': bool(frontmatter.get('meaning')),
        'has_translation': bool(frontmatter.get('translation', {}).get('en'))
    }

    # Add text validation if requested
    if validate_text and normative_verses is not None:
        validation = validate_verse_text(verse_id, frontmatter, normative_verses)
        result['validation'] = validation

    return result


def check_embeddings_status(project_dir: Path) -> Dict:
    """Check embeddings file status."""
    manifest_file = project_dir / "data" / "embeddings" / "collections" / "index.json"
    legacy_file = project_dir / "data" / "embeddings.json"

    if manifest_file.exists():
        try:
            with open(manifest_file, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            collection_counts = {}
            total = 0
            for item in manifest.get('collections', []):
                collection = item.get('collection', 'unknown')
                counts = item.get('counts', {})
                count = counts.get('total') or counts.get('en') or 0
                collection_counts[collection] = count
                total += count

            return {
                'exists': True,
                'verse_count': total,
                'collections': collection_counts,
                'file_info': get_file_info(manifest_file),
                'source': 'manifest'
            }
        except Exception as e:
            return {
                'exists': True,
                'error': str(e)
            }

    if not legacy_file.exists():
        return {
            'exists': False,
            'verse_count': 0,
            'collections': []
        }

    try:
        with open(legacy_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        collection_counts = defaultdict(int)
        verse_count = 0

        if isinstance(data, list):
            for item in data:
                collection = item.get('collection', 'unknown')
                collection_counts[collection] += 1
            verse_count = len(data)
        elif isinstance(data, dict):
            verses = data.get('verses')
            if isinstance(verses, dict):
                verse_count = len(verses.get('en', []))
                for item in verses.get('en', []):
                    collection = item.get('metadata', {}).get('collection_key', 'unknown')
                    collection_counts[collection] += 1
            elif isinstance(data.get('embeddings'), list):
                for item in data.get('embeddings', []):
                    collection = item.get('collection', 'unknown')
                    collection_counts[collection] += 1
                verse_count = len(data.get('embeddings', []))

        return {
            'exists': True,
            'verse_count': verse_count,
            'collections': dict(collection_counts),
            'file_info': get_file_info(legacy_file),
            'source': 'legacy'
        }
    except Exception as e:
        return {
            'exists': True,
            'error': str(e)
        }


def get_enabled_collections(project_dir: Path) -> List[Tuple[str, Dict]]:
    """Get list of enabled collections from collections.yml"""
    collections_file = project_dir / "_data" / "collections.yml"

    if not collections_file.exists():
        return []

    try:
        with open(collections_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        enabled = [
            (key, info)
            for key, info in data.items()
            if info.get('enabled', False)
        ]
        return enabled
    except Exception as e:
        print(f"Error reading collections.yml: {e}", file=sys.stderr)
        return []


def analyze_collection(
    collection: str,
    project_dir: Path,
    validate_text: bool = False,
    specific_verse: Optional[str] = None
) -> Dict:
    """Analyze a single collection."""
    verses_dir = project_dir / "_verses" / collection

    if not verses_dir.exists():
        return {
            'collection': collection,
            'exists': False,
            'error': f"Collection directory not found: {verses_dir}"
        }

    # Load normative verses if validation is requested
    normative_verses = None
    if validate_text:
        normative_verses = load_normative_verses(collection, project_dir)
        if not normative_verses:
            print(f"Warning: No normative verses found for {collection} at data/verses/{collection}.{{yaml,yml}}",
                  file=sys.stderr)

    # Find verse files
    if specific_verse:
        # Check specific verse only
        verse_file = verses_dir / f"{specific_verse}.md"
        if not verse_file.exists():
            return {
                'collection': collection,
                'exists': True,
                'error': f"Verse file not found: {verse_file}",
                'verse_count': 0,
                'verses': []
            }
        verse_files = [verse_file]
    else:
        # Check all verses
        verse_files = sorted(verses_dir.glob("*.md"))

    if not verse_files:
        return {
            'collection': collection,
            'exists': True,
            'verse_count': 0,
            'verses': []
        }

    # Analyze each verse
    verses = []
    for verse_file in verse_files:
        status = check_verse_status(
            collection,
            verse_file,
            project_dir,
            normative_verses=normative_verses,
            validate_text=validate_text
        )
        verses.append(status)

    # Calculate statistics
    total_verses = len(verses)
    verses_with_audio_full = sum(1 for v in verses if v['audio']['full'])
    verses_with_audio_slow = sum(1 for v in verses if v['audio']['slow'])
    verses_with_images = sum(1 for v in verses if v['images'])
    verses_with_devanagari = sum(1 for v in verses if v['has_devanagari'])
    verses_with_translation = sum(1 for v in verses if v['has_translation'])

    # Calculate completion percentage
    # Full completion = verse file + both audios + at least one image + devanagari + translation
    fully_complete = sum(
        1 for v in verses
        if v['audio']['full'] and v['audio']['slow'] and v['images']
        and v['has_devanagari'] and v['has_translation']
    )

    completion_percentage = (fully_complete / total_verses * 100) if total_verses > 0 else 0

    return {
        'collection': collection,
        'exists': True,
        'verse_count': total_verses,
        'statistics': {
            'completion_percentage': completion_percentage,
            'verses_complete': fully_complete,
            'verses_with_audio_full': verses_with_audio_full,
            'verses_with_audio_slow': verses_with_audio_slow,
            'verses_with_images': verses_with_images,
            'verses_with_devanagari': verses_with_devanagari,
            'verses_with_translation': verses_with_translation
        },
        'verses': verses
    }


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def print_collection_status(analysis: Dict, detailed: bool = False, show_validation: bool = False):
    """Print collection status in human-readable format."""
    collection = analysis['collection']

    if not analysis.get('exists'):
        print(f"\n✗ Collection '{collection}' not found")
        if 'error' in analysis:
            print(f"  {analysis['error']}")
        return

    verse_count = analysis['verse_count']

    if verse_count == 0:
        print(f"\n📚 Collection: {collection}")
        print("  ⚠ No verses found")
        return

    stats = analysis['statistics']

    print(f"\n📚 Collection: {collection}")
    print(f"   Verses: {verse_count}")
    print(f"   Completion: {stats['completion_percentage']:.1f}% ({stats['verses_complete']}/{verse_count} verses)")

    print("\n   Content Status:")
    print(f"   ├─ Devanagari text:  {stats['verses_with_devanagari']:3d}/{verse_count} verses")
    print(f"   ├─ Translation:      {stats['verses_with_translation']:3d}/{verse_count} verses")
    print(f"   ├─ Audio (full):     {stats['verses_with_audio_full']:3d}/{verse_count} verses")
    print(f"   ├─ Audio (slow):     {stats['verses_with_audio_slow']:3d}/{verse_count} verses")
    print(f"   └─ Images:           {stats['verses_with_images']:3d}/{verse_count} verses")

    # Show validation results
    if show_validation and analysis['verses']:
        verses_with_validation = [v for v in analysis['verses'] if 'validation' in v]

        if verses_with_validation:
            print("\n   Text Validation:")

            # Count validation statuses
            validation_counts = defaultdict(int)
            for verse in verses_with_validation:
                validation_counts[verse['validation']['status']] += 1

            print(f"   ├─ Exact match:      {validation_counts['match']:3d}/{len(verses_with_validation)} verses")
            print(f"   ├─ Minor diff:       {validation_counts['minor_diff']:3d}/{len(verses_with_validation)} verses")
            print(f"   ├─ Mismatch:         {validation_counts['mismatch']:3d}/{len(verses_with_validation)} verses")
            print(f"   └─ Missing:          {validation_counts['missing_normative']:3d}/{len(verses_with_validation)} verses")

            # Show details if requested or if there are issues
            if detailed or validation_counts['mismatch'] > 0 or validation_counts['minor_diff'] > 0:
                print("\n   Validation Details:")
                for verse in verses_with_validation:
                    verse_id = verse['verse_id']
                    validation = verse['validation']
                    status = validation['status']

                    # Status icons
                    status_icon = {
                        'match': '✓',
                        'minor_diff': '⚠️',
                        'mismatch': '✗',
                        'missing_normative': '✗',
                        'missing_verse': '✗'
                    }.get(status, '?')

                    print(f"   ├─ {verse_id:20s} {status_icon} {validation['message']}")

                    # Show details for mismatches
                    if status in ['mismatch', 'minor_diff'] and detailed:
                        if validation.get('normative_text') and validation.get('current_text'):
                            print(f"   │  ├─ Normative: {validation['normative_text'][:60]}...")
                            print(f"   │  └─ Current:   {validation['current_text'][:60]}...")
                    elif status == 'missing_normative':
                        print(f"   │  └─ Add to data/verses/{collection}.{{yaml,yml}}")
                    elif status == 'mismatch':
                        print(f"   │  └─ Fix: verse-generate --collection {collection} --verse {verse_id.split('_')[-1]} --fetch-text")
        else:
            print("\n   Text Validation:")
            print(f"   └─ No normative source found (data/verses/{collection}.{{yaml,yml}})")

    if detailed and not show_validation:
        print("\n   Verse Details:")
        for verse in analysis['verses']:
            verse_id = verse['verse_id']
            audio_full = "✓" if verse['audio']['full'] else "✗"
            audio_slow = "✓" if verse['audio']['slow'] else "✗"
            images = "✓" if verse['images'] else "✗"
            devanagari = "✓" if verse['has_devanagari'] else "✗"

            print(f"   ├─ {verse_id:20s} │ Text:{devanagari} │ Audio:{audio_full}{audio_slow} │ Image:{images}")

            # Show missing content
            missing = []
            if not verse['has_devanagari']:
                missing.append("devanagari")
            if not verse['audio']['full']:
                missing.append("audio_full")
            if not verse['audio']['slow']:
                missing.append("audio_slow")
            if not verse['images']:
                missing.append("images")

            if missing:
                print(f"   │  └─ Missing: {', '.join(missing)}")


def print_embeddings_status(embeddings: Dict):
    """Print embeddings status."""
    print("\n🔍 Embeddings Status:")

    if not embeddings['exists']:
        print("   ✗ No embeddings found (data/embeddings/collections/index.json)")
        print("   Run: verse-embeddings --multi-collection")
        return

    if 'error' in embeddings:
        print(f"   ✗ Error reading embeddings: {embeddings['error']}")
        return

    print(f"   ✓ Total verses indexed: {embeddings['verse_count']}")

    if embeddings['collections']:
        print("   Collections:")
        for collection, count in embeddings['collections'].items():
            print(f"   ├─ {collection:30s} {count:3d} verses")

    if 'file_info' in embeddings and embeddings['file_info']:
        info = embeddings['file_info']
        size = format_size(info['size'])
        modified = info['modified'].strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n   File: {info['path']}")
        print(f"   Size: {size}, Modified: {modified}")


def print_summary(analyses: List[Dict], embeddings: Dict):
    """Print overall summary."""
    total_verses = sum(a['verse_count'] for a in analyses if a.get('exists'))
    total_collections = len([a for a in analyses if a.get('exists')])

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Collections: {total_collections}")
    print(f"Total verses: {total_verses}")

    if embeddings.get('exists') and 'verse_count' in embeddings and 'error' not in embeddings:
        indexed = embeddings['verse_count']
        missing = total_verses - indexed
        if missing > 0:
            print(f"⚠ Verses not in embeddings: {missing}")
            print("  Run: verse-embeddings --multi-collection")
        else:
            print("✓ All verses indexed in embeddings")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check status of verse collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check specific collection
  verse-status --collection hanuman-chalisa

  # Check all enabled collections
  verse-status --all-collections

  # Validate text against normative source (data/verses/{collection}.yaml)
  verse-status --collection sundar-kaand --validate-text

  # Validate specific verse
  verse-status --collection sundar-kaand --verse chaupai_01 --validate-text

  # Detailed report with verse-by-verse breakdown
  verse-status --collection sundar-kaand --detailed --validate-text

  # JSON output for scripting
  verse-status --collection hanuman-chalisa --format json

  # Check embeddings status
  verse-status --embeddings-only
        """
    )

    parser.add_argument(
        "--collection",
        type=str,
        help="Collection key to check",
        metavar="KEY"
    )

    parser.add_argument(
        "--verse",
        type=str,
        help="Specific verse ID to check (e.g., chaupai_01, doha_05)",
        metavar="ID"
    )

    parser.add_argument(
        "--all-collections",
        action="store_true",
        help="Check all enabled collections"
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed verse-by-verse breakdown"
    )

    parser.add_argument(
        "--validate-text",
        action="store_true",
        help="Validate verse text against normative source (data/verses/{collection}.yaml)"
    )

    parser.add_argument(
        "--format",
        choices=['text', 'json'],
        default='text',
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--embeddings-only",
        action="store_true",
        help="Only check embeddings status"
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: current directory)"
    )

    args = parser.parse_args()

    project_dir = args.project_dir

    # Check embeddings status
    embeddings = check_embeddings_status(project_dir)

    if args.embeddings_only:
        if args.format == 'json':
            print(json.dumps(embeddings, indent=2, default=str))
        else:
            print_embeddings_status(embeddings)
        sys.exit(0)

    # Determine which collections to check
    collections_to_check = []

    if args.all_collections:
        enabled = get_enabled_collections(project_dir)
        collections_to_check = [key for key, _ in enabled]
    elif args.collection:
        collections_to_check = [args.collection]
    else:
        parser.error("Either --collection or --all-collections is required")

    if not collections_to_check:
        print("No collections found to check")
        sys.exit(1)

    # Analyze collections
    analyses = []
    for collection in collections_to_check:
        analysis = analyze_collection(
            collection,
            project_dir,
            validate_text=args.validate_text,
            specific_verse=args.verse
        )
        analyses.append(analysis)

    # Output results
    if args.format == 'json':
        output = {
            'collections': analyses,
            'embeddings': embeddings
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        # Print header
        print("\n" + "="*60)
        print("VERSE COLLECTION STATUS")
        print("="*60)

        # Print each collection
        for analysis in analyses:
            print_collection_status(
                analysis,
                detailed=args.detailed,
                show_validation=args.validate_text
            )

        # Print embeddings status
        print_embeddings_status(embeddings)

        # Print summary if multiple collections
        if len(analyses) > 1:
            print_summary(analyses, embeddings)

        print()


if __name__ == '__main__':
    main()
