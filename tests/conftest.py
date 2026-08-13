import numpy as np
import pytest
from PIL import Image


def _save(img: Image.Image, path) -> str:
    img.save(path)
    return str(path)


@pytest.fixture
def make_noise_image(tmp_path):
    """Factory fixture: make_noise_image(seed, name) -> path to a random-noise PNG.
    Random noise = lots of high-frequency content, useful as a stand-in for a
    'sharp' photo and for generating perceptually distinct images."""

    def _make(seed: int, name: str = "noise.png", size=(128, 128)):
        rng = np.random.default_rng(seed)
        arr = rng.integers(0, 256, size, dtype=np.uint8)
        img = Image.fromarray(arr, mode="L").convert("RGB")
        return _save(img, tmp_path / name)

    return _make


@pytest.fixture
def make_solid_image(tmp_path):
    def _make(value: int, name: str = "solid.png", size=(64, 64)):
        img = Image.new("L", size, color=value)
        return _save(img, tmp_path / name)

    return _make


@pytest.fixture
def make_blurred_copy(tmp_path):
    def _make(src_path: str, name: str = "blurred.png", radius: float = 5.0):
        from PIL import ImageFilter

        img = Image.open(src_path).filter(ImageFilter.GaussianBlur(radius=radius))
        return _save(img, tmp_path / name)

    return _make
