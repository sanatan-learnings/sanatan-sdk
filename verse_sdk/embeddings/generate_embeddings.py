#!/usr/bin/env python3
"""
Generate embeddings for verse-based texts.

This script reads all verse markdown files, extracts YAML front matter,
combines fields into rich semantic documents, and generates embeddings
using either OpenAI (default) or HuggingFace (local via sentence-transformers).

Usage as library:
    from verse_sdk.embeddings import generate_embeddings
    generate_embeddings(verses_dir, output_file, provider='openai')

Usage as script:
    python -m verse_sdk.embeddings.generate_embeddings --collection hanuman-chalisa --collections-file ./_data/collections.yml
    python -m verse_sdk.embeddings.generate_embeddings --multi-collection --collections-file ./_data/collections.yml
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available (CI/CD environment), use environment variables directly
    pass

# Provider configurations
PROVIDERS = {
    'openai': {
        'model': 'text-embedding-3-small',
        'dimensions': 1536,
        'cost_per_1m': 0.02,
        'requires_api_key': True,
        'backend': 'openai'
    },
    'bedrock-cohere': {
        'model': 'cohere.embed-multilingual-v3',
        'dimensions': 1024,
        'cost_per_1m': 0.10,
        'requires_api_key': False,
        'backend': 'bedrock',
        'max_input_chars': 2048
    },
    'huggingface': {
        'model': 'sentence-transformers/all-MiniLM-L6-v2',
        'dimensions': 384,
        'cost_per_1m': 0.0,  # Free (local)
        'requires_api_key': False,
        'backend': 'local'
    }
}


def get_openai_embedding(text, client, model):
    """Get embedding from OpenAI API."""
    try:
        response = client.embeddings.create(
            model=model,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"  Error: {e}")
        return None


def get_huggingface_embedding(text, model_instance):
    """Get embedding from local HuggingFace model."""
    try:
        # The model returns a list of embeddings (one per input)
        embedding = model_instance.encode([text])[0].tolist()
        return embedding
    except Exception as e:
        print(f"  Error: {e}")
        return None


def get_bedrock_embedding(text, client, config, input_type="search_document"):
    """Get embedding from Amazon Bedrock Cohere multilingual model."""
    import json
    try:
        response = client.invoke_model(
            modelId=config['model'],
            body=json.dumps({
                "texts": [text],
                "input_type": input_type
            }),
            contentType='application/json',
            accept='application/json'
        )
        response_body = json.loads(response['body'].read())
        return response_body['embeddings'][0]
    except Exception as e:
        print(f"  Error: {e}")
        return None


def initialize_provider(provider_name):
    """
    Initialize the embedding provider.

    Returns:
        tuple: (embedding_function, client_or_model, config)
    """
    config = PROVIDERS[provider_name]

    if provider_name == 'openai':
        from openai import OpenAI

        api_key = os.getenv('OPENAI_API_KEY', '')
        if not api_key:
            print("Error: OPENAI_API_KEY not found in .env file")
            sys.exit(1)

        client = OpenAI(api_key=api_key)
        print(f"✓ OpenAI client initialized (key: {api_key[:8]}...)")

        return get_openai_embedding, client, config

    elif provider_name == 'bedrock-cohere':
        try:
            import boto3
        except ImportError:
            print("Error: boto3 not installed")
            print("Run: pip install boto3")
            sys.exit(1)

        region = os.getenv('AWS_REGION', 'us-east-1')
        try:
            client = boto3.client(
                service_name='bedrock-runtime',
                region_name=region
            )
            print(f"✓ Bedrock client initialized (region: {region})")
            print(f"✓ Model: {config['model']}")
        except Exception as e:
            print(f"Error initializing Bedrock client: {e}")
            print("Configure AWS credentials: aws configure")
            sys.exit(1)

        return get_bedrock_embedding, client, config

    elif provider_name == 'huggingface':
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("Error: sentence-transformers not installed")
            print("Run: ./venv/bin/pip install sentence-transformers")
            sys.exit(1)

        print(f"Loading model {config['model']}...")
        model = SentenceTransformer(config['model'])
        print("✓ Model loaded successfully")

        return get_huggingface_embedding, model, config

    else:
        print(f"Error: Unknown provider '{provider_name}'")
        print(f"Available providers: {', '.join(PROVIDERS.keys())}")
        sys.exit(1)


def extract_yaml_frontmatter(file_path):
    """Extract YAML front matter from markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if not content.startswith('---'):
        return None

    end_idx = content.find('---', 3)
    if end_idx == -1:
        return None

    yaml_content = content[3:end_idx].strip()
    return yaml.safe_load(yaml_content)


def load_collections_config(collections_file):
    """Load collections configuration from YAML file."""
    if not collections_file.exists():
        print(f"Error: Collections file not found: {collections_file}")
        sys.exit(1)

    with open(collections_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_enabled_collections(collections_config):
    """Filter and return only enabled collections."""
    return {
        key: info for key, info in collections_config.items()
        if info.get('enabled', False)
    }


def build_document_parts(verse_data, lang='en'):
    """
    Build ordered document parts from verse data.

    Combines multiple fields to capture full spiritual context:
    - Title (semantic anchor)
    - Transliteration (Sanskrit/Hindi terminology)
    - Literal Translation (basic meaning)
    - Interpretive Meaning (spiritual depth)
    - Story (mythological context)
    - Practical Application (teaching + when to use)
    """
    parts = []

    # Title
    title_key = f'title_{lang}'
    if title_key in verse_data:
        parts.append((title_key, verse_data[title_key]))

    # Transliteration (same for both languages)
    if 'transliteration' in verse_data:
        parts.append(("transliteration", f"Transliteration: {verse_data['transliteration']}"))

    # Literal Translation
    lit_key = 'literal_translation'
    if lit_key in verse_data:
        lit_data = verse_data[lit_key]
        if isinstance(lit_data, dict) and lang in lit_data:
            parts.append(("literal_translation", f"Translation: {lit_data[lang]}"))

    # Interpretive Meaning
    meaning_key = 'interpretive_meaning'
    if meaning_key in verse_data:
        meaning_data = verse_data[meaning_key]
        if isinstance(meaning_data, dict) and lang in meaning_data:
            parts.append(("interpretive_meaning", f"Meaning: {meaning_data[lang]}"))

    # Story
    if 'story' in verse_data:
        story_data = verse_data['story']
        if isinstance(story_data, dict) and lang in story_data:
            parts.append(("story", f"Story: {story_data[lang]}"))

    # Practical Application
    if 'practical_application' in verse_data:
        app_data = verse_data['practical_application']

        # Teaching
        if 'teaching' in app_data:
            teaching = app_data['teaching']
            if isinstance(teaching, dict) and lang in teaching:
                parts.append(("teaching", f"Teaching: {teaching[lang]}"))

        # When to use
        if 'when_to_use' in app_data:
            when = app_data['when_to_use']
            if isinstance(when, dict) and lang in when:
                parts.append(("when_to_use", f"When to Use: {when[lang]}"))

    return parts


def build_document(verse_data, lang='en'):
    parts = [text for _, text in build_document_parts(verse_data, lang)]
    return "\n\n".join(parts)


def reduce_document(verse_data, lang, max_chars, policy):
    parts = build_document_parts(verse_data, lang)
    if max_chars is None:
        combined = "\n\n".join(text for _, text in parts)
        return combined, False, len(combined)

    combined = "\n\n".join(text for _, text in parts)
    if len(combined) <= max_chars:
        return combined, False, len(combined)

    reduced_parts = []
    current_len = 0
    for _, text in parts:
        if not reduced_parts:
            next_len = len(text)
        else:
            next_len = current_len + 2 + len(text)

        if next_len <= max_chars:
            reduced_parts.append(text)
            current_len = next_len
            continue

        if policy == "truncate" or not reduced_parts:
            remaining = max_chars - current_len
            if reduced_parts and remaining > 2:
                remaining -= 2
            if remaining > 0:
                reduced_parts.append(text[:remaining])
            current_len = max_chars
        break

    reduced = "\n\n".join(reduced_parts)
    return reduced, True, len(combined)


def average_embeddings(embeddings):
    if not embeddings:
        return None
    length = len(embeddings[0])
    totals = [0.0] * length
    for emb in embeddings:
        for i, value in enumerate(emb):
            totals[i] += value
    return [value / len(embeddings) for value in totals]


def embed_text(
    text,
    embed_func,
    client_or_model,
    config,
    backend,
    max_input_chars=None,
    truncate_policy="drop",
):
    if backend == 'bedrock' and max_input_chars and len(text) > max_input_chars:
        if truncate_policy == "chunk":
            chunks = [
                text[i:i + max_input_chars]
                for i in range(0, len(text), max_input_chars)
            ]
            print(f"  Bedrock input too long; chunking into {len(chunks)} parts")
            embeddings = []
            for chunk in chunks:
                embeddings.append(embed_func(chunk, client_or_model, config))
            return average_embeddings(embeddings)

    if backend == 'bedrock':
        return embed_func(text, client_or_model, config)
    if backend == 'openai':
        return embed_func(text, client_or_model, config['model'])
    return embed_func(text, client_or_model)


def extract_permalink_from_frontmatter(verse_data):
    """Extract permalink from verse frontmatter if available."""
    return verse_data.get('permalink', None)


def generate_verse_url(verse_data):
    """Generate URL path for verse page."""
    verse_num = verse_data.get('verse_number', 0)

    # Handle special cases (dohas, closing verses)
    title_en = verse_data.get('title_en', '')
    if 'Doha' in title_en:
        if 'Opening' in title_en or verse_num == 1 or verse_num == '1':
            return '/verses/doha-01/'
        elif verse_num == 2 or verse_num == '2':
            return '/verses/doha-02/'
    elif 'Closing' in title_en:
        return '/verses/doha-closing/'

    # Ensure verse_num is an integer for formatting
    if isinstance(verse_num, str):
        try:
            verse_num = int(verse_num)
        except ValueError:
            verse_num = 0

    return f'/verses/verse-{verse_num:02d}/'


def process_verse_file(
    file_path,
    embed_func,
    client_or_model,
    config,
    collection_metadata=None,
    provider_name=None,
    max_input_chars=None,
    truncate_policy="drop",
):
    """Process a single verse file and return metadata + embeddings.

    Args:
        file_path: Path to the verse markdown file
        embed_func: Embedding generation function
        client_or_model: API client or local model instance
        config: Provider configuration dict
        collection_metadata: Optional dict with 'key' and 'name' for multi-collection mode
    """
    print(f"Processing {file_path.name}...")

    verse_data = extract_yaml_frontmatter(file_path)
    if not verse_data:
        print(f"  Warning: Could not extract YAML from {file_path.name}")
        return None

    verse_num = verse_data.get('verse_number', 0)

    # Build documents for both languages
    if truncate_policy == "chunk":
        doc_en = build_document(verse_data, 'en')
        doc_hi = build_document(verse_data, 'hi')
        reduced_en = False
        reduced_hi = False
        orig_len_en = len(doc_en)
        orig_len_hi = len(doc_hi)
    else:
        doc_en, reduced_en, orig_len_en = reduce_document(verse_data, 'en', max_input_chars, truncate_policy)
        doc_hi, reduced_hi, orig_len_hi = reduce_document(verse_data, 'hi', max_input_chars, truncate_policy)

    # Get embeddings
    backend = config.get('backend', 'openai')

    print("  Getting English embedding...")
    if reduced_en:
        print(f"  Warning: Reduced English input length for {provider_name or backend} ({orig_len_en} → {len(doc_en)} chars, max {max_input_chars})")
    emb_en = embed_text(
        doc_en,
        embed_func,
        client_or_model,
        config,
        backend,
        max_input_chars=max_input_chars,
        truncate_policy=truncate_policy,
    )

    if backend in ('openai', 'bedrock'):
        time.sleep(0.1)

    print("  Getting Hindi embedding...")
    if reduced_hi:
        print(f"  Warning: Reduced Hindi input length for {provider_name or backend} ({orig_len_hi} → {len(doc_hi)} chars, max {max_input_chars})")
    emb_hi = embed_text(
        doc_hi,
        embed_func,
        client_or_model,
        config,
        backend,
        max_input_chars=max_input_chars,
        truncate_policy=truncate_policy,
    )

    if backend in ('openai', 'bedrock'):
        time.sleep(0.1)

    if not emb_en or not emb_hi:
        print(f"  Warning: Failed to get embeddings for {file_path.name}")
        return None

    # Determine URL: use permalink from frontmatter if available, otherwise generate
    permalink = extract_permalink_from_frontmatter(verse_data)
    verse_url = permalink if permalink else generate_verse_url(verse_data)

    # Prepare base metadata
    base_metadata = {
        'devanagari': verse_data.get('devanagari', ''),
        'transliteration': verse_data.get('transliteration', ''),
    }

    # Add collection metadata if in multi-collection mode
    if collection_metadata:
        base_metadata['collection_key'] = collection_metadata['key']
        base_metadata['collection_name'] = collection_metadata['name']

    # Prepare result structure
    result = {
        'en': {
            'verse_number': verse_num,
            'title': verse_data.get('title_en', ''),
            'url': verse_url,
            'embedding': emb_en,
            'metadata': {
                **base_metadata,
                'literal_translation': verse_data.get('literal_translation', {}).get('en', '')
            }
        },
        'hi': {
            'verse_number': verse_num,
            'title': verse_data.get('title_hi', ''),
            'url': verse_url,
            'embedding': emb_hi,
            'metadata': {
                **base_metadata,
                'literal_translation': verse_data.get('literal_translation', {}).get('hi', '')
            }
        }
    }

    return result


def process_single_collection(
    verses_dir,
    embed_func,
    client_or_model,
    config,
    collection_metadata=None,
    provider_name=None,
    max_input_chars=None,
    truncate_policy="drop",
):
    """Process verses from a single directory (backward compatibility mode)."""
    # Check verses directory
    if not verses_dir.exists():
        print(f"Error: Verses directory not found: {verses_dir}")
        sys.exit(1)

    # Find all verse files
    verse_files = sorted(verses_dir.glob("*.md"))
    print(f"Found {len(verse_files)} verse files")
    print()

    # Process all verses
    verses_en = []
    verses_hi = []

    for verse_file in verse_files:
        result = process_verse_file(
            verse_file, embed_func, client_or_model, config,
            collection_metadata=collection_metadata,
            provider_name=provider_name,
            max_input_chars=max_input_chars,
            truncate_policy=truncate_policy,
        )
        if result:
            verses_en.append(result['en'])
            verses_hi.append(result['hi'])
        print()

    # Sort by verse number
    verses_en.sort(key=lambda v: int(v['verse_number']) if isinstance(v['verse_number'], (int, str)) and str(v['verse_number']).isdigit() else 999)
    verses_hi.sort(key=lambda v: int(v['verse_number']) if isinstance(v['verse_number'], (int, str)) and str(v['verse_number']).isdigit() else 999)

    return verses_en, verses_hi


def process_multi_collection(
    collections_file,
    base_verses_dir,
    embed_func,
    client_or_model,
    config,
    provider_name=None,
    max_input_chars=None,
    truncate_policy="drop",
):
    """Process verses from multiple collections."""
    # Load collections configuration
    collections_config = load_collections_config(collections_file)
    enabled_collections = get_enabled_collections(collections_config)

    if not enabled_collections:
        print("Error: No enabled collections found in collections file")
        sys.exit(1)

    print(f"Found {len(enabled_collections)} enabled collection(s):")
    for key, info in enabled_collections.items():
        print(f"  - {key}: {info.get('name_en', key)}")
    print()

    # Process each collection
    outputs = []

    for coll_key, coll_info in enabled_collections.items():
        print("=" * 70)
        print(f"Processing collection: {coll_key}")
        print("=" * 70)

        # Get collection subdirectory
        subdirectory = coll_info.get('subdirectory', coll_key)
        verses_dir = base_verses_dir / subdirectory

        if not verses_dir.exists():
            print(f"Warning: Verses directory not found: {verses_dir}")
            print(f"Skipping collection: {coll_key}")
            print()
            continue

        # Prepare collection metadata
        collection_metadata = {
            'key': coll_key,
            'name': coll_info.get('name_en', coll_key)
        }

        verses_en, verses_hi = process_single_collection(
            verses_dir, embed_func, client_or_model, config,
            collection_metadata=collection_metadata,
            provider_name=provider_name,
            max_input_chars=max_input_chars,
            truncate_policy=truncate_policy,
        )

        outputs.append({
            'collection': coll_key,
            'collection_name': collection_metadata['name'],
            'verses_en': verses_en,
            'verses_hi': verses_hi
        })

        print(f"Completed collection: {coll_key}")
        print()

    return outputs


def build_collection_output(collection_key, provider_name, config, verses_en, verses_hi, collection_name=None):
    output = {
        'collection': collection_key,
        'model': config['model'],
        'dimensions': config['dimensions'],
        'provider': provider_name,
        'generated_at': datetime.now().isoformat(),
        'verses': {
            'en': verses_en,
            'hi': verses_hi
        }
    }
    if collection_name:
        output['collection_name'] = collection_name
    return output


def write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def normalize_payload(payload: dict) -> dict:
    """Return a copy of the payload without volatile fields."""
    if not isinstance(payload, dict):
        return payload
    cleaned = dict(payload)
    cleaned.pop("generated_at", None)
    if "collections" in cleaned and isinstance(cleaned["collections"], list):
        cleaned["collections"] = sorted(
            cleaned["collections"],
            key=lambda item: item.get("collection", "") if isinstance(item, dict) else ""
        )
    if "verses" in cleaned and isinstance(cleaned["verses"], dict):
        cleaned["verses"] = {
            k: cleaned["verses"][k] for k in ("en", "hi") if k in cleaned["verses"]
        }
    return cleaned


def write_collection_file(output_dir: Path, collection_key: str, payload: dict) -> dict:
    output_path = output_dir / f"{collection_key}.json"
    existing_checksum = None
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_payload = json.load(f)
            if normalize_payload(existing_payload) == normalize_payload(payload):
                existing_checksum = compute_sha256(output_path)
                print(f"  Collection {collection_key} unchanged; skipping write")
        except Exception:
            existing_checksum = None
    if existing_checksum is None:
        write_json_file(output_path, payload)
        checksum = compute_sha256(output_path)
    else:
        checksum = existing_checksum
    counts = {
        'en': len(payload.get('verses', {}).get('en', [])),
        'hi': len(payload.get('verses', {}).get('hi', []))
    }
    return {
        'collection': collection_key,
        'path': output_path.name,
        'counts': {
            **counts,
            'total': counts['en']
        },
        'checksum': checksum,
        'model': payload.get('model'),
        'dimensions': payload.get('dimensions'),
        'provider': payload.get('provider'),
    }


def write_manifest(output_dir: Path, entries: list) -> Path:
    manifest = {
        'collections': entries
    }
    manifest_path = output_dir / "index.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            if normalize_payload(existing) == normalize_payload(manifest):
                print("index.json unchanged; skipping write")
                return manifest_path
        except Exception:
            pass
    write_json_file(manifest_path, manifest)
    print("index.json updated (reason: content changed)")
    return manifest_path


def main():
    """Main execution flow."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Generate embeddings for verse-based texts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single collection mode (backward compatible)
  python generate_embeddings.py --collection hanuman-chalisa --collections-file ./_data/collections.yml

  # Multi-collection mode
  python generate_embeddings.py --multi-collection --collections-file ./_data/collections.yml
  python generate_embeddings.py --multi-collection --collections-file ./collections.yml --provider huggingface

  # Legacy combined output (opt-in)
  python generate_embeddings.py --multi-collection --collections-file ./_data/collections.yml --legacy-output
        """
    )
    parser.add_argument(
        '--provider',
        choices=['openai', 'bedrock-cohere', 'huggingface'],
        default=os.getenv('EMBEDDING_PROVIDER', 'openai'),
        help='Embedding provider to use (default: from EMBEDDING_PROVIDER env var or "openai")'
    )
    parser.add_argument(
        '--verses-dir',
        type=Path,
        default=Path.cwd() / "_verses",
        help='Directory containing verse markdown files (default: ./_verses)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Legacy combined output file path (requires --legacy-output)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path.cwd() / "data" / "embeddings" / "collections",
        help='Output directory for per-collection embeddings (default: ./data/embeddings/collections)'
    )
    parser.add_argument(
        '--collection',
        type=str,
        help='Collection key to process (single collection mode)'
    )
    parser.add_argument(
        '--multi-collection',
        action='store_true',
        help='Enable multi-collection mode'
    )
    parser.add_argument(
        '--collections-file',
        type=Path,
        help='Path to collections.yml file (required for multi-collection mode)'
    )
    parser.add_argument(
        '--max-input-chars',
        type=int,
        default=None,
        help='Max input characters per embedding request (provider-specific default if omitted)'
    )
    parser.add_argument(
        '--truncate-policy',
        choices=['drop', 'truncate', 'chunk'],
        default='drop',
        help='How to handle inputs exceeding max length: drop sections, truncate, or chunk+average'
    )
    parser.add_argument(
        '--legacy-output',
        action='store_true',
        help='Write legacy combined embeddings output (opt-in)'
    )

    args = parser.parse_args()
    provider_name = args.provider
    verses_dir = args.verses_dir
    output_file = args.output
    output_dir = args.output_dir
    collection_key = args.collection
    legacy_output = args.legacy_output
    truncate_policy = args.truncate_policy
    multi_collection = args.multi_collection
    collections_file = args.collections_file

    # Validate arguments
    if multi_collection and not collections_file:
        print("Error: --collections-file is required when using --multi-collection")
        sys.exit(1)
    if output_file and not legacy_output:
        print("Warning: --output implies legacy output. Use --legacy-output explicitly.")
        legacy_output = True

    print("=" * 70)
    print("Verse Embeddings Generator")
    print("=" * 70)

    # Initialize provider
    embed_func, client_or_model, config = initialize_provider(provider_name)
    max_input_chars = args.max_input_chars or config.get('max_input_chars')

    print(f"Provider: {provider_name}")
    print(f"Model: {config['model']}")
    print(f"Dimensions: {config['dimensions']}")
    if max_input_chars:
        print(f"Max input chars: {max_input_chars} (policy: {truncate_policy})")

    if multi_collection:
        print("Mode: Multi-collection")
        print(f"Collections file: {collections_file}")
        print(f"Base verses directory: {verses_dir}")
    else:
        print("Mode: Single collection")
        print(f"Verses directory: {verses_dir}")
        if collection_key:
            print(f"Collection key: {collection_key}")

    print(f"Output dir: {output_dir}")
    if legacy_output:
        print(f"Legacy output file: {output_file or (Path.cwd() / 'data' / 'embeddings.json')}")
    print()

    # Process verses
    if multi_collection:
        collection_outputs = process_multi_collection(
            collections_file,
            verses_dir,
            embed_func,
            client_or_model,
            config,
            provider_name=provider_name,
            max_input_chars=max_input_chars,
            truncate_policy=truncate_policy,
        )
    else:
        collection_name = None
        if collections_file and collection_key:
            collections_config = load_collections_config(collections_file)
            collection_info = collections_config.get(collection_key, {})
            if not collection_info:
                print(f"Error: Collection '{collection_key}' not found in {collections_file}")
                sys.exit(1)
            collection_name = collection_info.get('name_en', collection_key)
            subdirectory = collection_info.get('subdirectory', collection_key)
            verses_dir = verses_dir / subdirectory
        elif collection_key:
            if verses_dir.name != collection_key:
                candidate_dir = verses_dir / collection_key
                if candidate_dir.exists():
                    verses_dir = candidate_dir
        else:
            if verses_dir.name != "_verses":
                collection_key = verses_dir.name
                collection_name = collection_key

        if not collection_key:
            print("Error: --collection is required for per-collection output")
            sys.exit(1)

        collection_metadata = {
            'key': collection_key,
            'name': collection_name or collection_key
        }
        verses_en, verses_hi = process_single_collection(
            verses_dir,
            embed_func,
            client_or_model,
            config,
            collection_metadata=collection_metadata,
            provider_name=provider_name,
            max_input_chars=max_input_chars,
            truncate_policy=truncate_policy,
        )
        collection_outputs = [{
            'collection': collection_key,
            'collection_name': collection_metadata['name'],
            'verses_en': verses_en,
            'verses_hi': verses_hi
        }]

    manifest_entries = []
    for output_item in collection_outputs:
        payload = build_collection_output(
            output_item['collection'],
            provider_name,
            config,
            output_item['verses_en'],
            output_item['verses_hi'],
            collection_name=output_item.get('collection_name')
        )
        entry = write_collection_file(output_dir, output_item['collection'], payload)
        manifest_entries.append(entry)

    manifest_entries.sort(key=lambda item: item.get("collection", ""))
    manifest_path = write_manifest(output_dir, manifest_entries)

    if legacy_output:
        if output_file is None:
            output_file = Path.cwd() / "data" / "embeddings.json"
        output = {
            'model': config['model'],
            'dimensions': config['dimensions'],
            'provider': provider_name,
            'generated_at': datetime.now().isoformat(),
            'verses': {
                'en': [v for item in collection_outputs for v in item['verses_en']],
                'hi': [v for item in collection_outputs for v in item['verses_hi']]
            }
        }
        print(f"Writing legacy embeddings to {output_file}...")
        write_json_file(output_file, output)

    print()
    print("=" * 70)
    print("Generation Complete!")
    print("=" * 70)
    total_en = sum(len(item['verses_en']) for item in collection_outputs)
    total_hi = sum(len(item['verses_hi']) for item in collection_outputs)
    print(f"Total verses processed: {total_en}")
    print(f"English embeddings: {total_en}")
    print(f"Hindi embeddings: {total_hi}")
    print(f"Manifest: {manifest_path}")
    if legacy_output and output_file:
        print(f"Legacy output size: {output_file.stat().st_size / 1024:.1f} KB")

    # Calculate approximate cost
    total_embeddings = total_en + total_hi
    if config['cost_per_1m'] > 0:
        approx_tokens = total_embeddings * 750  # Rough estimate
        cost = (approx_tokens / 1_000_000) * config['cost_per_1m']
        print(f"Approximate cost: ${cost:.4f} ({config['model']} @ ${config['cost_per_1m']}/1M tokens)")
    else:
        print("Cost: FREE (local model)")
    print()


if __name__ == '__main__':
    main()
