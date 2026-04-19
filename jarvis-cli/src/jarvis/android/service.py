"""Helpers for booting an Android emulator and running APK files."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class AndroidError(RuntimeError):
    """Raised when Android tooling operations fail."""


@dataclass(slots=True)
class AndroidRunResult:
    """Result of installing and optionally launching an APK."""

    apk_path: Path
    serial: str
    avd_name: str | None
    package_name: str
    launched: bool
    booted_emulator: bool


def run_apk(
    apk_path: str | Path,
    *,
    avd_name: str | None = None,
    reinstall: bool = False,
    launch: bool = True,
    timeout_seconds: int = 180,
) -> AndroidRunResult:
    """Install an APK on an emulator and optionally launch it."""
    resolved_apk = _resolve_apk_path(apk_path)
    adb_path = _find_adb()
    emulator_path = _find_emulator()
    aapt_path = _find_aapt()

    available_avds = list_avds(emulator_path=emulator_path)
    serial = get_running_emulator_serial(adb_path=adb_path)
    booted_emulator = False
    selected_avd = avd_name

    if serial is None:
        selected_avd = _select_avd(avd_name, available_avds)
        serial = boot_emulator(
            selected_avd,
            emulator_path=emulator_path,
            adb_path=adb_path,
            timeout_seconds=timeout_seconds,
        )
        booted_emulator = True

    package_name = get_package_name(resolved_apk, aapt_path=aapt_path)
    install_apk(
        resolved_apk,
        adb_path=adb_path,
        serial=serial,
        reinstall=reinstall,
    )

    if launch:
        launch_app(package_name, adb_path=adb_path, serial=serial)

    return AndroidRunResult(
        apk_path=resolved_apk,
        serial=serial,
        avd_name=selected_avd,
        package_name=package_name,
        launched=launch,
        booted_emulator=booted_emulator,
    )


def list_avds(*, emulator_path: str | None = None) -> list[str]:
    """Return available Android Virtual Devices."""
    emulator = emulator_path or _find_emulator()
    result = _run_command([emulator, "-list-avds"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_running_emulator_serial(*, adb_path: str | None = None) -> str | None:
    """Return the first running emulator serial, if any."""
    adb = adb_path or _find_adb()
    result = _run_command([adb, "devices"])
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device" and parts[0].startswith("emulator-"):
            return parts[0]
    return None


def boot_emulator(
    avd_name: str,
    *,
    emulator_path: str | None = None,
    adb_path: str | None = None,
    timeout_seconds: int = 180,
) -> str:
    """Start an emulator and wait until it is fully booted."""
    emulator = emulator_path or _find_emulator()
    adb = adb_path or _find_adb()

    existing = set(_list_connected_serials(adb))
    subprocess.Popen(
        [emulator, "-avd", avd_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + timeout_seconds
    candidate_serial: str | None = None

    while time.time() < deadline:
        current = set(_list_connected_serials(adb))
        new_emulators = [serial for serial in current - existing if serial.startswith("emulator-")]
        if new_emulators:
            candidate_serial = sorted(new_emulators)[0]
        elif candidate_serial is None:
            running_emulators = [serial for serial in current if serial.startswith("emulator-")]
            if running_emulators:
                candidate_serial = sorted(running_emulators)[0]

        if candidate_serial and _is_device_boot_completed(adb, candidate_serial):
            return candidate_serial

        time.sleep(2)

    raise AndroidError(f"Timed out waiting for emulator '{avd_name}' to boot")


def install_apk(
    apk_path: str | Path,
    *,
    adb_path: str | None = None,
    serial: str | None = None,
    reinstall: bool = False,
) -> None:
    """Install an APK on the target device."""
    resolved_apk = _resolve_apk_path(apk_path)
    adb = adb_path or _find_adb()
    command = _adb_command(adb, serial) + ["install"]
    if reinstall:
        command.append("-r")
    command.append(str(resolved_apk))
    _run_command(command)


def get_package_name(apk_path: str | Path, *, aapt_path: str | None = None) -> str:
    """Extract the Android package name from an APK file."""
    resolved_apk = _resolve_apk_path(apk_path)
    aapt = aapt_path or _find_aapt()
    result = _run_command([aapt, "dump", "badging", str(resolved_apk)])
    match = re.search(r"package: name='([^']+)'", result.stdout)
    if not match:
        raise AndroidError(f"Could not determine package name for '{resolved_apk}'")
    return match.group(1)


def launch_app(package_name: str, *, adb_path: str | None = None, serial: str | None = None) -> None:
    """Launch an installed Android application."""
    adb = adb_path or _find_adb()
    command = _adb_command(adb, serial) + [
        "shell",
        "monkey",
        "-p",
        package_name,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    ]
    _run_command(command)


def _resolve_apk_path(apk_path: str | Path) -> Path:
    path = Path(apk_path).expanduser().resolve()
    if not path.exists():
        raise AndroidError(f"APK not found: {path}")
    if not path.is_file():
        raise AndroidError(f"APK path is not a file: {path}")
    if path.suffix.lower() != ".apk":
        raise AndroidError(f"Expected an .apk file, got: {path.name}")
    return path


def _find_adb() -> str:
    return _find_tool("adb", sdk_relative_path="platform-tools/adb")


def _find_emulator() -> str:
    return _find_tool("emulator", sdk_relative_path="emulator/emulator")


def _find_aapt() -> str:
    direct = shutil.which("aapt")
    if direct:
        return direct

    sdk_root = _sdk_root()
    if sdk_root is None:
        raise AndroidError("Android SDK not found. Set ANDROID_HOME or install Android Studio.")

    build_tools_dir = sdk_root / "build-tools"
    if not build_tools_dir.exists():
        raise AndroidError("Android build-tools not found in the SDK.")

    versions = sorted([path for path in build_tools_dir.iterdir() if path.is_dir()])
    for version in reversed(versions):
        candidate = version / "aapt"
        if candidate.exists():
            return str(candidate)

    raise AndroidError("Could not find 'aapt' in Android build-tools.")


def _find_tool(name: str, *, sdk_relative_path: str) -> str:
    direct = shutil.which(name)
    if direct:
        return direct

    sdk_root = _sdk_root()
    if sdk_root is not None:
        candidate = sdk_root / sdk_relative_path
        if candidate.exists():
            return str(candidate)

    raise AndroidError(
        f"Could not find '{name}'. Install Android SDK tools and ensure they are on PATH."
    )


def _sdk_root() -> Path | None:
    candidates = [
        Path.home() / "Library/Android/sdk",
    ]

    for env_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        raw = os.environ.get(env_var)
        if raw:
            candidates.insert(0, Path(raw).expanduser())

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _select_avd(requested_avd: str | None, available_avds: list[str]) -> str:
    if requested_avd:
        if requested_avd not in available_avds:
            available = ", ".join(available_avds) if available_avds else "none"
            raise AndroidError(f"AVD '{requested_avd}' not found. Available AVDs: {available}")
        return requested_avd

    if len(available_avds) == 1:
        return available_avds[0]
    if not available_avds:
        raise AndroidError("No Android Virtual Devices found. Create one in Android Studio first.")

    available = ", ".join(available_avds)
    raise AndroidError(f"Multiple AVDs found. Choose one with --avd. Available AVDs: {available}")


def _adb_command(adb_path: str, serial: str | None) -> list[str]:
    command = [adb_path]
    if serial:
        command.extend(["-s", serial])
    return command


def _list_connected_serials(adb_path: str) -> list[str]:
    result = _run_command([adb_path, "devices"])
    serials: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def _is_device_boot_completed(adb_path: str, serial: str) -> bool:
    command = [adb_path, "-s", serial, "shell", "getprop", "sys.boot_completed"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.returncode == 0 and result.stdout.strip() == "1"


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise AndroidError(message)
    return result
