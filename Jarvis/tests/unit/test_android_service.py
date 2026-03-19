"""Tests for Android APK service helpers."""

from pathlib import Path

import pytest

from jarvis.android.service import AndroidError, _resolve_apk_path, _select_avd


class TestResolveApkPath:
    """Tests for APK path validation."""

    def test_resolve_existing_apk(self, tmp_path: Path) -> None:
        apk = tmp_path / "demo.apk"
        apk.write_bytes(b"apk")

        assert _resolve_apk_path(apk) == apk.resolve()

    def test_missing_apk_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(AndroidError, match="APK not found"):
            _resolve_apk_path(tmp_path / "missing.apk")

    def test_non_apk_extension_raises_error(self, tmp_path: Path) -> None:
        text_file = tmp_path / "demo.txt"
        text_file.write_text("nope")

        with pytest.raises(AndroidError, match=r"Expected an \.apk file"):
            _resolve_apk_path(text_file)


class TestSelectAvd:
    """Tests for AVD selection logic."""

    def test_select_requested_avd(self) -> None:
        assert _select_avd("Pixel_8", ["Pixel_8", "Tablet"]) == "Pixel_8"

    def test_auto_select_single_avd(self) -> None:
        assert _select_avd(None, ["Medium_Phone_API_36.1"]) == "Medium_Phone_API_36.1"

    def test_missing_requested_avd_raises_error(self) -> None:
        with pytest.raises(AndroidError, match="AVD 'Missing' not found"):
            _select_avd("Missing", ["Pixel_8"])

    def test_multiple_avds_require_explicit_choice(self) -> None:
        with pytest.raises(AndroidError, match="Multiple AVDs found"):
            _select_avd(None, ["Pixel_8", "Tablet"])

    def test_no_avds_raises_error(self) -> None:
        with pytest.raises(AndroidError, match="No Android Virtual Devices found"):
            _select_avd(None, [])
