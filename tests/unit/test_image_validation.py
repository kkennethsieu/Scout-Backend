"""Unit tests for image validation in storage_service.py.

Tests the _validate_image_content function with real image bytes.
"""

import io

import pytest
from PIL import Image

from app.core.exceptions import PhotoInvalidFormat
from app.services.storage_service import _validate_image_content


def _make_jpeg_bytes(width=100, height=100) -> bytes:
    """Create a minimal valid JPEG image in memory."""
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_bytes(width=100, height=100) -> bytes:
    """Create a minimal valid PNG image in memory."""
    img = Image.new("RGB", (width, height), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestValidateImageContent:
    """Test image content validation."""

    def test_valid_jpeg_accepted(self):
        """Real JPEG bytes pass validation."""
        data = _make_jpeg_bytes()
        _validate_image_content(data)  # Should not raise

    def test_png_rejected(self):
        """Real PNG bytes are rejected — JPEG only."""
        data = _make_png_bytes()
        with pytest.raises(PhotoInvalidFormat):
            _validate_image_content(data)

    def test_text_file_rejected(self):
        """Plain text renamed as .jpg is rejected."""
        data = b"This is not an image file at all"
        with pytest.raises(PhotoInvalidFormat):
            _validate_image_content(data)

    def test_truncated_jpeg_rejected(self):
        """Truncated/corrupt JPEG bytes are rejected."""
        data = _make_jpeg_bytes()
        # Truncate to just the header
        truncated = data[:50]
        with pytest.raises(PhotoInvalidFormat):
            _validate_image_content(truncated)

    def test_empty_bytes_rejected(self):
        """Empty bytes are rejected."""
        with pytest.raises(PhotoInvalidFormat):
            _validate_image_content(b"")

    def test_gif_rejected(self):
        """GIF format is rejected — JPEG only."""
        img = Image.new("RGB", (10, 10), color="green")
        buf = io.BytesIO()
        img.save(buf, format="GIF")
        with pytest.raises(PhotoInvalidFormat):
            _validate_image_content(buf.getvalue())

    def test_bmp_rejected(self):
        """BMP format is rejected — JPEG only."""
        img = Image.new("RGB", (10, 10), color="yellow")
        buf = io.BytesIO()
        img.save(buf, format="BMP")
        with pytest.raises(PhotoInvalidFormat):
            _validate_image_content(buf.getvalue())

    def test_random_bytes_rejected(self):
        """Random garbage bytes are rejected."""
        import os

        data = os.urandom(1024)
        with pytest.raises(PhotoInvalidFormat):
            _validate_image_content(data)
