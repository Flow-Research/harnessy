from pathlib import Path

from jarvis.reading_list.models import SourceType
from jarvis.reading_list.source_loader import autodetect_source


def test_autodetect_source_anytype_url() -> None:
    target = "https://object.any.coop/bafyreibiaubmpvf6oidqwjxm3c3jzsgbq5eie4pagzmekr64cebuzabvwy?spaceId=abc"
    assert autodetect_source(target) == SourceType.ANYTYPE


def test_autodetect_source_file(tmp_path: Path) -> None:
    path = tmp_path / "reading.md"
    path.write_text("hello")
    assert autodetect_source(str(path)) == SourceType.FILE


def test_autodetect_source_stdin() -> None:
    assert autodetect_source("-") == SourceType.STDIN
