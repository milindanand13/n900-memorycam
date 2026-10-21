#!/usr/bin/env python3
"""Find archive photos that look like an N900 photo, using local CLIP image features.

Example, from the repository root:
    python3 scripts/match_archive.py --query private/inbox/20261009_017.jpg \
        --archive /path/to/older/photos

Photos are read in place and never changed or uploaded. Matching uses image
features only: captions, filenames, folders and dates do not affect the order.
Results, cached features and private preview images are written under private/.
The CLIP model is loaded from private/models/. Pass --download-model once to
fetch it; after that, every run stays offline.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import random
import time

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIVATE = REPO_ROOT / 'private'
MODEL_ID = 'openai/clip-vit-base-patch32'
MODEL_CACHE = PRIVATE / 'models' / 'huggingface'
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff'}
RANDOM_SEED = 11
MATCHES_SHOWN = 6


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def ranking(query_vector, vectors, records, query_hash):
    """Rank records by cosine similarity to the query, leaving out copies of the query."""
    q = np.asarray(query_vector, dtype=np.float32)
    v = np.asarray(vectors, dtype=np.float32)
    if not np.isfinite(q).all() or not np.isfinite(v).all():
        raise ValueError('Nonfinite image features')
    qnorm = np.linalg.norm(q)
    norms = np.linalg.norm(v, axis=1)
    if qnorm == 0 or np.any(norms == 0):
        raise ValueError('Zero image features')
    scores = np.sum((v / norms[:, None]) * (q / qnorm), axis=1, dtype=np.float64)
    if not np.isfinite(scores).all():
        raise ValueError('Nonfinite similarity scores')
    result = [{**record, 'score': float(score)} for record, score in zip(records, scores)
              if record['sha256'] != query_hash]
    return sorted(result, key=lambda r: (-r['score'], r['relative_path']))


def unique_images(paths, source, checksum=sha256):
    """Split image paths into unique records and exact-byte duplicate copies."""
    records, duplicates, seen = [], [], set()
    for path in paths:
        record = {'relative_path': str(path.relative_to(source)), 'sha256': checksum(path)}
        if record['sha256'] in seen:
            duplicates.append(record)
        else:
            seen.add(record['sha256'])
            records.append(record)
    return records, duplicates


def inside_private(path):
    resolved = path.resolve()
    return resolved == PRIVATE.resolve() or PRIVATE.resolve() in resolved.parents


def load_rgb(path):
    from PIL import Image, ImageOps
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert('RGB')


def write_review(output, query, source, ranked, baseline):
    from PIL import Image
    assets = output / 'review-images'
    assets.mkdir(exist_ok=True)
    shown = [('N900 photo', query, query.name)] + [
        ('Match {}'.format(i), source / r['relative_path'], r['relative_path'])
        for i, r in enumerate(ranked[:MATCHES_SHOWN], 1)
    ] + [('Random comparison', source / baseline['relative_path'], baseline['relative_path'])]
    cards = []
    for i, (label, path, caption) in enumerate(shown):
        image = load_rgb(path)
        image.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
        image.save(assets / '{}.jpg'.format(i), quality=90)
        image.close()
        cards.append('<figure><img src="review-images/{}.jpg" alt="{}"><figcaption>{}<small>{}</small>'
                     '</figcaption></figure>'.format(i, html.escape(label), html.escape(label),
                                                     html.escape(caption)))
    page = (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Memorycam matches</title><style>'
        'body{background:#171717;color:#eee;font:18px system-ui;max-width:1500px;margin:40px auto;padding:0 24px}'
        'h1{font:36px Georgia}p{max-width:850px;line-height:1.5;color:#ccc}'
        '.photos{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}figure{margin:0}'
        'img{width:100%;height:340px;object-fit:contain;background:#222}figcaption{margin:12px 0 24px}'
        'small{display:block;color:#aaa;overflow-wrap:anywhere;font-size:13px;margin-top:8px}'
        '@media(max-width:850px){.photos{grid-template-columns:1fr}}</style>'
        '<h1>Memorycam matches</h1>'
        '<p>One N900 photo searched against {} unique archive photos using image features only. '
        'The six closest matches, then one random pick for comparison (it may also be a match).</p>'
        '<div class="photos">{}</div>'
        '<p>Visual similarity, not a judgment of meaning. Originals are unchanged; these are private previews.</p>'
        '</html>'
    ).format(len(ranked), ''.join(cards))
    (output / 'review.html').write_text(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--query', type=Path, required=True, help='The N900 photo to match')
    parser.add_argument('--archive', type=Path, required=True, help='Folder of older photos (searched recursively)')
    parser.add_argument('--output', type=Path, help='Results folder under private/ (default: private/matches/<time>)')
    parser.add_argument('--feature-cache', type=Path, help='Folder under private/ for cached features '
                        '(default: private/features), shared between runs')
    parser.add_argument('--download-model', action='store_true', help='Allow a one-time CLIP download into private/models/')
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = (args.output or PRIVATE / 'matches' / stamp).resolve()
    cache = (args.feature_cache or PRIVATE / 'features').resolve()
    for label, path in (('Output', output), ('Feature cache', cache)):
        if not inside_private(path):
            parser.error('{} must stay inside private/, which git ignores.'.format(label))
    source = args.archive.resolve()
    query = args.query.resolve()
    if not source.is_dir():
        parser.error('Archive folder not found: {}'.format(source))
    if not query.is_file():
        parser.error('Query photo not found: {}'.format(query))
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    paths = sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    records, duplicates = unique_images(paths, source)
    if not records:
        raise SystemExit('No photos found in the archive folder.')
    query_hash = sha256(query)
    print(json.dumps({'files': len(paths), 'unique_images': len(records),
                      'duplicate_copies': len(duplicates)}), flush=True)

    import torch
    from transformers import CLIPImageProcessor, CLIPModel
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    offline = not args.download_model
    try:
        model = CLIPModel.from_pretrained(MODEL_ID, cache_dir=MODEL_CACHE, local_files_only=offline).eval().to(device)
        processor = CLIPImageProcessor.from_pretrained(MODEL_ID, cache_dir=MODEL_CACHE, local_files_only=offline)
    except OSError:
        raise SystemExit('CLIP is not in private/models/ yet. Run once with --download-model.')
    revision = (MODEL_CACHE / 'models--openai--clip-vit-base-patch32' / 'refs' / 'main').read_text().strip()

    start = time.monotonic()
    vectors = []
    items = [(query, query_hash)] + [(source / r['relative_path'], r['sha256']) for r in records]
    for number, (path, checksum) in enumerate(items, 1):
        feature_path = cache / '{}-{}.npy'.format(checksum, revision)
        if feature_path.exists():
            vector = np.load(feature_path, allow_pickle=False)
        else:
            image = load_rgb(path)
            try:
                pixels = processor(images=image, return_tensors='pt')['pixel_values'].to(device)
                with torch.inference_mode():
                    vector = model.get_image_features(pixel_values=pixels)[0].cpu().numpy()
            finally:
                image.close()
            np.save(feature_path, vector, allow_pickle=False)
        vectors.append(vector)
        if number == 1 or number % 25 == 0 or number == len(items):
            print(json.dumps({'processed': number, 'total': len(items),
                              'elapsed_seconds': round(time.monotonic() - start, 1), 'device': device}), flush=True)

    ranked = ranking(vectors[0], vectors[1:], records, query_hash)
    if not ranked:
        raise SystemExit('No archive photos left after excluding copies of the query.')
    baseline = random.Random(RANDOM_SEED).choice(sorted(ranked, key=lambda r: r['relative_path']))
    for record in records + duplicates:
        if sha256(source / record['relative_path']) != record['sha256']:
            raise SystemExit('An archive photo changed during the run: ' + record['relative_path'])
    if sha256(query) != query_hash:
        raise SystemExit('The query photo changed during the run.')

    result = {
        'created_utc': datetime.now(timezone.utc).isoformat(), 'model': MODEL_ID, 'model_revision': revision,
        'method': 'Cosine similarity of CLIP image features', 'source': str(source),
        'source_files': len(paths), 'unique_images': len(records), 'duplicate_copies': len(duplicates),
        'eligible_candidates': len(ranked), 'query': str(query), 'query_sha256': query_hash,
        'ranking': ranked, 'random_baseline': baseline, 'random_seed': RANDOM_SEED,
        'originals_unchanged': True, 'device': device, 'elapsed_seconds': round(time.monotonic() - start, 3),
        'limitations': ['Visual similarity, not a measure of memory value',
                        'No date filtering or face recognition',
                        'Exact-byte deduplication only; near-duplicates can both rank highly'],
    }
    (output / 'result.json').write_text(json.dumps(result, indent=2))
    write_review(output, query, source, ranked, baseline)
    print(json.dumps({'review': str(output / 'review.html'), 'top_match': ranked[0]}), flush=True)


if __name__ == '__main__':
    main()
