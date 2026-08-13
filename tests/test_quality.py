from analyze_and_backup.quality import (
    blur_score,
    exposure_metrics,
    is_bad_exposure,
    is_blurry,
)


def test_blurred_image_scores_lower_than_sharp(make_noise_image, make_blurred_copy):
    sharp = make_noise_image(seed=0, name="sharp.png")
    blurred = make_blurred_copy(sharp, name="blurred.png", radius=5.0)

    sharp_score = blur_score(sharp)
    blurred_score = blur_score(blurred)

    assert sharp_score > blurred_score
    assert is_blurry(blurred_score, threshold=100.0)
    assert not is_blurry(sharp_score, threshold=100.0)


def test_overexposed_image_flagged(make_solid_image):
    white = make_solid_image(255, name="white.png")
    metrics = exposure_metrics(white)

    assert metrics.clipped_high_pct == 1.0
    bad, reasons = is_bad_exposure(
        metrics, clip_pct_threshold=0.05, luminance_min=40.0, luminance_max=215.0
    )
    assert bad
    assert any("white" in r for r in reasons)


def test_underexposed_image_flagged(make_solid_image):
    black = make_solid_image(0, name="black.png")
    metrics = exposure_metrics(black)

    assert metrics.clipped_low_pct == 1.0
    bad, reasons = is_bad_exposure(
        metrics, clip_pct_threshold=0.05, luminance_min=40.0, luminance_max=215.0
    )
    assert bad
    assert any("black" in r for r in reasons)


def test_well_exposed_image_not_flagged(make_solid_image):
    mid_gray = make_solid_image(128, name="gray.png")
    metrics = exposure_metrics(mid_gray)

    assert metrics.mean_luminance == 128.0
    bad, reasons = is_bad_exposure(
        metrics, clip_pct_threshold=0.05, luminance_min=40.0, luminance_max=215.0
    )
    assert not bad
    assert reasons == []
