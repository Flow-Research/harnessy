import socket

import pytest

from jarvis.reading_list.parser import extract_reading_items
from jarvis.reading_list.source_loader import load_source_document


def anytype_available() -> bool:
    """Check whether the local AnyType desktop API is reachable."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            return sock.connect_ex(("localhost", 31009)) == 0
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not anytype_available(),
        reason="AnyType desktop app not running on localhost:31009",
    ),
]


def test_load_real_anytype_reading_list() -> None:
    target = (
        "https://object.any.coop/"
        "bafyreibiaubmpvf6oidqwjxm3c3jzsgbq5eie4pagzmekr64cebuzabvwy"
        "?spaceId=bafyreicffftqmjc67fcgwd6ogwpft2rvprr2m3lnkoubhn4ezkx6eexcty.1pwez68b32cu5"
    )
    source = load_source_document(target, resolver=None, backend="anytype")
    assert source.title == "Read"
    items = extract_reading_items(source.markdown)
    assert len(items) >= 80
