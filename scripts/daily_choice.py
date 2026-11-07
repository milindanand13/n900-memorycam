#!/usr/bin/env python3
"""Choose the one N900 photo Memorycam uses as the night's query.

Example, from the repository root (a dry run: nothing is saved):
    python3 scripts/daily_choice.py --date 2026-10-24

Rule: take the photos whose camera filename carries the chosen date. Drop the
unusable ones (too dark, too blurry, or a near copy of a later shot that day),
then pick the one CLIP finds most scene-like (a place, an activity, people in
context) rather than a mirror selfie or an object close-up. CLIP sees dark
photos lifted to a readable brightness, and a dark photo loses a little score
so a lit one wins when the two are close. If every photo is unusable, the best
of them is still used. With no photo that day, the stand-in
is the best usable older photo in the library that was never chosen before.
Photos with a wrong camera clock count only if their date is in CLOCK_FIXES.

Photos are read in place and never changed or uploaded. Add --record only when
the choice is really used (printing); it appends to the ignored
private/daily-choice.json, which stops a photo being chosen twice and makes a
repeated run on the same date return the same photo. Exit status 2 means there
is nothing left to choose.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path

import numpy as np

import match_archive as match
from photo_library import configured_root, date_folders, validate_root

LEDGER = match.PRIVATE / 'daily-choice.json'
TOKENIZER = match.PRIVATE / 'models' / 'clip-tokenizer'
MIN_BLUR = 30.0         # variance of the Laplacian on a 512 px copy; the lowest ~5% of real photos
MIN_BRIGHTNESS = 8.0    # mean grey level, 0 to 255; below this there is nothing to see even when lifted
BRIGHTEN_BELOW = 110.0  # photos darker than this mean level are lifted to it before CLIP sees them
DARK_FULL = 70.0        # mean grey level at and above which a photo loses no score for darkness
DARK_PENALTY = 0.03     # score a black photo loses, shrinking to nothing at DARK_FULL
NEAR_COPY = 0.95        # CLIP cosine at which two shots count as the same picture
# The N900 clock restarted at 2009-01-01 on 2026-09-11 and counted up a day at a time until it was fixed on
# 2026-09-29. Only the filename dates checked against Google Photos are listed, so 20090114 and 20090118 stay out.
CLOCK_FIXES = {'20090101': date(2026, 9, 11), '20090110': date(2026, 9, 20),
               '20090113': date(2026, 9, 23), '20090119': date(2026, 9, 29)}
# Internal prompts that steer the score; they are never shown or printed.
SCENE_PROMPTS = ['a photo of a place or landscape', 'people together doing an activity',
                 'a street or city scene', 'a meal or event with friends', 'a scenic view outdoors']
NOT_SCENE_PROMPTS = ['a selfie in a mirror', 'a close-up photo of an object', 'a close-up portrait of a face',
                     'a photo of a screen or a document', 'a photo of a blank wall or ceiling']


def photo_day(name, today):
    """The camera-filename date (corrected through CLOCK_FIXES), or None when it is unverified or in the future."""
    fixed = CLOCK_FIXES.get(Path(name).name[:8])
    if fixed:
        return fixed
    folder = date_folders(name, today=today)
    return None if folder.name == 'Date-unverified' else date.fromisoformat(folder.name)


def unit(vectors):
    v = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(v, axis=-1, keepdims=True)
    if not np.isfinite(v).all() or np.any(norms == 0):
        raise ValueError('Unusable image features')
    return v / norms


def scene_scores(vectors, scene, not_scene):
    """Closest scene prompt minus closest non-scene prompt, per photo."""
    v = unit(vectors)
    return (v @ unit(scene).T).max(axis=1) - (v @ unit(not_scene).T).max(axis=1)


def near_copies(vectors):
    """Indexes of photos that have a near-identical later photo; the later one stays."""
    v = unit(vectors)
    sims = v @ v.T
    return {i for i in range(len(v)) if np.any(sims[i, i + 1:] >= NEAR_COPY)}


def lifted(pixels):
    """RGB pixels (0 to 255) lifted by a gamma curve up to mean BRIGHTEN_BELOW, and whether they were lifted."""
    a = np.asarray(pixels, dtype=np.float64) / 255.0
    mean = float(a.mean()) * 255
    if mean >= BRIGHTEN_BELOW:
        return np.asarray(pixels), False
    gamma = min(1.0, max(0.25, np.log(BRIGHTEN_BELOW / 255) / np.log(max(mean, 1.0) / 255)))
    return (np.power(a, gamma) * 255).clip(0, 255).astype(np.uint8), True


def dark_penalty(brightness):
    return DARK_PENALTY * max(0.0, (DARK_FULL - brightness) / DARK_FULL)


def photo_problems(blur, brightness):
    return (['blurry'] if blur < MIN_BLUR else []) + (['too dark'] if brightness < MIN_BRIGHTNESS else [])


def photo_quality(path):
    gray = match.load_rgb(path).convert('L')
    gray.thumbnail((512, 512))
    a = np.asarray(gray, dtype=np.float64)
    laplacian = 4 * a[1:-1, 1:-1] - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    return float(laplacian.var()), float(a.mean())


def pick(candidates):
    """Best-scoring usable photo; if none is usable, the best of all. Ties go to the later name."""
    pool = [c for c in candidates if not c['problems']] or candidates
    return max(pool, key=lambda c: (c['scene'], c['name'])) if pool else None


def library_photos(root):
    return sorted((p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in match.IMAGE_SUFFIXES),
                  key=lambda p: p.name)


def load_ledger(path=LEDGER):
    return json.loads(path.read_text())['choices'] if path.exists() else []


def record_choice(entry, path=LEDGER):
    choices = load_ledger(path) + [entry]
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'choices': choices}, indent=2))
    os.replace(temporary, path)


def choose_photo(root, day, used, quality, embed, score):
    """Return the day's choice. `quality(path)`, `embed(paths)` and `score(vectors)` are the model-side steps."""
    photos = library_photos(root)
    todays = [p for p in photos if photo_day(p.name, day) == day]
    source = 'today' if todays else 'stand-in'
    if todays:
        paths = todays
    else:
        paths, seen = [], set(used)
        for p in (p for p in photos if (photo_day(p.name, day - timedelta(days=1)) or day) < day):
            digest = match.sha256(p)
            if digest not in seen:
                seen.add(digest)
                paths.append(p)
    if not paths:
        return {'date': day.isoformat(), 'source': 'none', 'chosen': None, 'considered': []}
    vectors = embed(paths)
    scenes = score(vectors)
    copies = near_copies(vectors)
    candidates = []
    for i, path in enumerate(paths):
        blur, brightness = quality(path)
        problems = photo_problems(blur, brightness) + (['near copy'] if i in copies else [])
        candidates.append({'name': path.name, 'path': str(path.relative_to(root)), 'scene': float(scenes[i]) - dark_penalty(brightness),
                           'blur': round(blur, 1), 'brightness': round(brightness, 1), 'problems': problems})
    chosen = pick(candidates)
    return {'date': day.isoformat(), 'source': source, 'chosen': chosen['path'],
            'used_despite_problems': chosen['problems'], 'considered': candidates}


def clip_steps():
    """Local CLIP: image features (cached next to the matcher's) and the prompt-based scene score."""
    import torch
    from transformers import CLIPImageProcessor, CLIPModel, CLIPTokenizer
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    try:
        model = CLIPModel.from_pretrained(match.MODEL_ID, cache_dir=match.MODEL_CACHE, local_files_only=True).eval().to(device)
        processor = CLIPImageProcessor.from_pretrained(match.MODEL_ID, cache_dir=match.MODEL_CACHE, local_files_only=True)
        tokenizer = CLIPTokenizer.from_pretrained(TOKENIZER, local_files_only=True)
    except OSError:
        raise SystemExit('CLIP or its tokenizer is not in private/models/. Run match_archive.py --download-model first.')
    revision = (match.MODEL_CACHE / 'models--openai--clip-vit-base-patch32' / 'refs' / 'main').read_text().strip()
    cache = match.PRIVATE / 'features'
    cache.mkdir(parents=True, exist_ok=True)

    def embed(paths):
        vectors = []
        for path in paths:
            image = match.load_rgb(path)
            try:
                pixels, dark = lifted(np.asarray(image))
                # A lifted photo has its own cache file; the matcher's file for the same photo stays untouched.
                feature_path = cache / '{}-{}{}.npy'.format(match.sha256(path), revision, '-lifted' if dark else '')
                if feature_path.exists():
                    vectors.append(np.load(feature_path, allow_pickle=False))
                    continue
                if dark:
                    from PIL import Image
                    image.close()
                    image = Image.fromarray(pixels)
                values = processor(images=image, return_tensors='pt')['pixel_values'].to(device)
                with torch.inference_mode():
                    vector = model.get_image_features(pixel_values=values)[0].cpu().numpy()
            finally:
                image.close()
            np.save(feature_path, vector, allow_pickle=False)
            vectors.append(vector)
        return vectors

    def text(prompts):
        tokens = tokenizer(prompts, padding=True, return_tensors='pt').to(device)
        with torch.inference_mode():
            return model.get_text_features(**tokens).cpu().numpy()

    scene, not_scene = text(SCENE_PROMPTS), text(NOT_SCENE_PROMPTS)
    return embed, lambda vectors: scene_scores(vectors, scene, not_scene)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--date', type=date.fromisoformat, default=date.today(), help='Day to choose for (default: today)')
    parser.add_argument('--library', type=Path, help='Photo library (default: the one set by organize_photos.py)')
    parser.add_argument('--record', action='store_true', help='Save the choice so it is never chosen again')
    args = parser.parse_args()

    root = validate_root(args.library, match.REPO_ROOT) if args.library else configured_root(match.PRIVATE, match.REPO_ROOT)
    if root is None or not root.is_dir():
        raise SystemExit('Photo library not found. Run organize_photos.py first, or pass --library.')
    ledger = load_ledger()
    earlier = [c for c in ledger if c['date'] == args.date.isoformat()]
    if earlier:
        print(json.dumps({'date': args.date.isoformat(), 'already_recorded': earlier[-1]}, indent=2))
        return
    embed, score = clip_steps()
    result = choose_photo(root, args.date, {c['sha256'] for c in ledger}, photo_quality, embed, score)
    print(json.dumps(result, indent=2))
    if result['chosen'] is None:
        raise SystemExit(2)
    if args.record:
        record_choice({'date': result['date'], 'source': result['source'], 'path': result['chosen'],
                       'sha256': match.sha256(root / result['chosen']),
                       'recorded_utc': datetime.now(timezone.utc).isoformat()})


if __name__ == '__main__':
    main()
