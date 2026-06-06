from jarvis.knowledge_body import strip_duplicate_title_heading


def test_strips_duplicate_leading_h1() -> None:
    body = "# Deep Research\n\nActual body."

    assert strip_duplicate_title_heading(body, "Deep Research") == "Actual body."


def test_strips_duplicate_h1_when_journal_title_has_day_prefix() -> None:
    body = "# Deep Research\n\nActual body."

    assert strip_duplicate_title_heading(body, "5 - Deep Research") == "Actual body."


def test_strips_duplicate_h1_when_generated_title_keeps_hash() -> None:
    body = "# Deep Research\n\nActual body."

    assert strip_duplicate_title_heading(body, "# Deep Research") == "Actual body."


def test_preserves_non_matching_h1() -> None:
    body = "# Different Heading\n\nActual body."

    assert strip_duplicate_title_heading(body, "Deep Research") == body


def test_preserves_frontmatter_and_strips_following_duplicate_h1() -> None:
    body = "---\nstatus: draft\n---\n\n# Deep Research\n\nActual body."

    assert (
        strip_duplicate_title_heading(body, "Deep Research")
        == "---\nstatus: draft\n---\n\nActual body."
    )
