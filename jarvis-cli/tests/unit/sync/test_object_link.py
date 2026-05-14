"""Tests for jarvis.sync.object_link."""

from __future__ import annotations

import pytest

from jarvis.sync.object_link import AnytypeLink, InvalidLinkError, parse_link


class TestParseLink:
    def test_anytype_scheme_full(self) -> None:
        link = parse_link("anytype://object?objectId=obj_abc&spaceId=space_xyz")
        assert link == AnytypeLink(object_id="obj_abc", space_id="space_xyz")

    def test_anytype_scheme_query_order_irrelevant(self) -> None:
        link = parse_link("anytype://object?spaceId=space_xyz&objectId=obj_abc")
        assert link.object_id == "obj_abc"
        assert link.space_id == "space_xyz"

    def test_https_anytype_io(self) -> None:
        link = parse_link("https://anytype.io/object/obj_abc?spaceId=space_xyz")
        assert link == AnytypeLink(object_id="obj_abc", space_id="space_xyz")

    def test_https_any_coop_single_segment_path(self) -> None:
        # The Anytype web client uses object.any.coop with a one-segment path.
        link = parse_link("https://object.any.coop/bafyreiABC?spaceId=bafyreiSPACE.suffix")
        assert link.object_id == "bafyreiABC"
        assert link.space_id == "bafyreiSPACE.suffix"

    def test_extras_in_query_and_fragment_ignored(self) -> None:
        url = (
            "https://object.any.coop/bafyreiABC"
            "?spaceId=bafyreiSPACE.suffix"
            "&inviteId=bafybeiINVITE"
            "#some-fragment-key"
        )
        link = parse_link(url)
        assert link.object_id == "bafyreiABC"
        assert link.space_id == "bafyreiSPACE.suffix"

    def test_http_also_accepted(self) -> None:
        # Some exports use http; we accept both.
        link = parse_link("http://anytype.io/object/obj_abc?spaceId=space_xyz")
        assert link.object_id == "obj_abc"

    def test_raw_pair(self) -> None:
        link = parse_link("obj_abc:space_xyz")
        assert link == AnytypeLink(object_id="obj_abc", space_id="space_xyz")

    def test_strips_whitespace(self) -> None:
        link = parse_link("   anytype://object?objectId=a&spaceId=b   ")
        assert link == AnytypeLink(object_id="a", space_id="b")

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "   ",
            "not-a-link",
            "anytype://object",  # no query
            "anytype://object?objectId=a",  # missing spaceId
            "anytype://object?spaceId=b",  # missing objectId
            "anytype://object?objectId=&spaceId=b",  # empty objectId
            "https://anytype.io/object/abc",  # no spaceId param
            "https://example.com/?spaceId=b",  # has spaceId but no path/object id
            ":space_only",  # bad raw
            "object_only:",  # bad raw
            "a:b:c",  # too many colons
        ],
    )
    def test_invalid_inputs_raise(self, bad: str) -> None:
        with pytest.raises(InvalidLinkError):
            parse_link(bad)

    def test_none_input_raises(self) -> None:
        with pytest.raises(InvalidLinkError):
            parse_link(None)  # type: ignore[arg-type]
