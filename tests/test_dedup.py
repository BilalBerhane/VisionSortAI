from analyze_and_backup.dedup import (
    DuplicateIndex,
    compute_phash,
    hamming_distance,
    resolve_duplicate,
)


def test_identical_images_are_duplicates(make_noise_image):
    a = make_noise_image(seed=0, name="a.png")
    b = make_noise_image(seed=0, name="b.png")  # same seed = identical pixels

    dist = hamming_distance(compute_phash(a), compute_phash(b))
    assert dist == 0
    assert dist <= 8  # default threshold


def test_different_images_are_not_duplicates(make_noise_image):
    a = make_noise_image(seed=0, name="a.png")
    b = make_noise_image(seed=42, name="b.png")

    dist = hamming_distance(compute_phash(a), compute_phash(b))
    assert dist > 8


def test_duplicate_index_finds_match_within_threshold(make_noise_image):
    index = DuplicateIndex(threshold=8)
    a = make_noise_image(seed=0, name="a.png")
    b = make_noise_image(seed=0, name="b.png")

    index.add(a, compute_phash(a), blur_score=50.0)
    match = index.find_duplicate(compute_phash(b))
    assert match is not None
    assert match.path == a


def test_duplicate_index_no_match_for_distinct_image(make_noise_image):
    index = DuplicateIndex(threshold=8)
    a = make_noise_image(seed=0, name="a.png")
    b = make_noise_image(seed=42, name="b.png")

    index.add(a, compute_phash(a), blur_score=50.0)
    assert index.find_duplicate(compute_phash(b)) is None


def test_resolve_duplicate_keeps_sharper_photo(make_noise_image):
    index = DuplicateIndex(threshold=8)
    a = make_noise_image(seed=0, name="a.png")
    entry = index.add(a, compute_phash(a), blur_score=50.0)

    b = make_noise_image(seed=0, name="b.png")
    resolution = resolve_duplicate(entry, b, candidate_blur_score=120.0)  # sharper

    assert resolution.keep_path == b
    assert resolution.delete_path == entry.path


def test_resolve_duplicate_keeps_existing_when_sharper(make_noise_image):
    index = DuplicateIndex(threshold=8)
    a = make_noise_image(seed=0, name="a.png")
    entry = index.add(a, compute_phash(a), blur_score=200.0)

    b = make_noise_image(seed=0, name="b.png")
    resolution = resolve_duplicate(entry, b, candidate_blur_score=10.0)  # blurrier

    assert resolution.keep_path == entry.path
    assert resolution.delete_path == b
