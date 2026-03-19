"""Android CLI commands."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from jarvis.android.service import AndroidError, list_avds, run_apk

console = Console()


@click.group(name="android")
def android_cli() -> None:
    """Run Android emulator and APK workflows."""
    pass


@android_cli.command(name="run")
@click.argument("apk_path", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option("--avd", "avd_name", default=None, help="AVD name to boot if no emulator is running")
@click.option(
    "--reinstall",
    is_flag=True,
    help="Reinstall the app if it is already installed",
)
@click.option("--no-launch", is_flag=True, help="Install the APK without launching the app")
@click.option(
    "--timeout",
    default=180,
    show_default=True,
    help="Seconds to wait for the emulator to finish booting",
)
def run_command(
    apk_path: str,
    avd_name: str | None,
    reinstall: bool,
    no_launch: bool,
    timeout: int,
) -> None:
    """Install an APK on an Android emulator and optionally launch it."""
    console.print(f"[dim]APK:[/dim] {apk_path}")

    try:
        with console.status("Preparing Android tools..."):
            result = run_apk(
                apk_path,
                avd_name=avd_name,
                reinstall=reinstall,
                launch=not no_launch,
                timeout_seconds=timeout,
            )
    except AndroidError as exc:
        console.print(f"[red]✗ Android run failed:[/red] {exc}")
        raise SystemExit(1)

    console.print()
    console.print("[green]✓ APK installed successfully[/green]")
    console.print(f"  [dim]Package:[/dim] {result.package_name}")
    console.print(f"  [dim]Device:[/dim]  {result.serial}")
    if result.avd_name:
        console.print(f"  [dim]AVD:[/dim]     {result.avd_name}")
    if result.booted_emulator:
        console.print("  [dim]Emulator:[/dim] started by Jarvis")
    if result.launched:
        console.print("  [dim]Launch:[/dim]  app opened")
    else:
        console.print("  [dim]Launch:[/dim]  skipped (--no-launch)")


@android_cli.command(name="avds")
def avds_command() -> None:
    """List available Android Virtual Devices."""
    try:
        avds = list_avds()
    except AndroidError as exc:
        console.print(f"[red]✗ Could not list AVDs:[/red] {exc}")
        raise SystemExit(1)

    if not avds:
        console.print("[yellow]No Android Virtual Devices found.[/yellow]")
        return

    table = Table(title="Android Virtual Devices", show_header=True, header_style="bold cyan")
    table.add_column("AVD Name", style="cyan")
    for avd in avds:
        table.add_row(avd)
    console.print(table)


@click.command(name="apk")
@click.argument("apk_path", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option("--avd", "avd_name", default=None, help="AVD name to boot if no emulator is running")
@click.option(
    "--reinstall",
    is_flag=True,
    help="Reinstall the app if it is already installed",
)
@click.option("--no-launch", is_flag=True, help="Install the APK without launching the app")
@click.option(
    "--timeout",
    default=180,
    show_default=True,
    help="Seconds to wait for the emulator to finish booting",
)
@click.pass_context
def quick_apk(
    ctx: click.Context,
    apk_path: str,
    avd_name: str | None,
    reinstall: bool,
    no_launch: bool,
    timeout: int,
) -> None:
    """Quick alias for 'android run'."""
    ctx.invoke(
        run_command,
        apk_path=apk_path,
        avd_name=avd_name,
        reinstall=reinstall,
        no_launch=no_launch,
        timeout=timeout,
    )
