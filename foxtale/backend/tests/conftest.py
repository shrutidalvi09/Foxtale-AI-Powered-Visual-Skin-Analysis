"""Shared pytest fixtures. Every test gets its own temporary FOXTALE_DATA_DIR so tests never
touch the real local database, and the camera/webcam is never opened (consistent with the
rest of this project's testing rules)."""

import os
import tempfile

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("FOXTALE_DATA_DIR", str(tmp_path / "foxtale_test_data"))
    # Re-import storage's module-level nothing is cached at import time (data_dir() reads the
    # env var fresh every call), so no reload is needed.
    yield


@pytest.fixture
def sample_face_image() -> np.ndarray:
    """A plain skin-tone-ish synthetic image, large enough for the crop/resize pipeline to run
    on. Not meant to look like a real face -- face detection is mocked in these tests."""
    rng = np.random.default_rng(0)
    img = np.full((480, 400, 3), (140, 170, 210), dtype=np.uint8)
    img += rng.integers(-5, 5, img.shape, dtype=np.int16).astype(np.uint8)
    return img


@pytest.fixture
def sample_face_box():
    return (40, 40, 320, 400)
