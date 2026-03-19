"""URL content fetching for reading list items."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import io
import logging
import re
import time
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from urllib.parse import urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .cache import URLCache, ttl_days_for_url
from .models import FetchedContent, ReadingItem, timestamp_now

_ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5}(?:v\d+)?)")
_TWEET_ID_RE = re.compile(r"(?:twitter\.com|x\.com)/[^/]+/status/(\d+)")
_GITHUB_REPO_RE = re.compile(r"github\.com/([^/]+)/([^/?#]+)")


async def _to_thread(func, /, *args, **kwargs):
    return await asyncio.to_thread(functools.partial(func, *args, **kwargs))


class PoliteClient:
    def __init__(self) -> None:
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._delays = {
            "export.arxiv.org": 3.0,
            "api.github.com": 0.75,
            "api.twitter.com": 1.0,
            "publish.twitter.com": 1.0,
            "api.fxtwitter.com": 0.5,
        }
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": "JarvisReadingList/0.1 (+https://github.com/Flow-Research/flow-network)",
            },
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        domain = self._domain(url)
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            delay = self._delays.get(domain, 1.0)
            elapsed = time.monotonic() - self._last_request.get(domain, 0.0)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
            response = await self.client.get(url, **kwargs)
            self._last_request[domain] = time.monotonic()
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", str(delay * 2)))
                await asyncio.sleep(min(retry_after, 60.0))
                response = await self.client.get(url, **kwargs)
                self._last_request[domain] = time.monotonic()
            response.raise_for_status()
            return response

    async def aclose(self) -> None:
        await self.client.aclose()


async def fetch_arxiv(url: str, client: PoliteClient) -> tuple[str, str, list[str]]:
    match = _ARXIV_ID_RE.search(url)
    arxiv_id = match.group(1) if match else url.rstrip("/").rsplit("/", 1)[-1].replace(".pdf", "")
    resp = await client.get(f"http://export.arxiv.org/api/query?id_list={arxiv_id}")
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)
    entry = root.find("atom:entry", ns)
    if entry is None:
        return "", "", []
    title = (
        (entry.findtext("atom:title", default="", namespaces=ns) or "").strip().replace("\n", " ")
    )
    abstract = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
    authors = [
        (author.findtext("atom:name", default="", namespaces=ns) or "").strip()
        for author in entry.findall("atom:author", ns)
    ]
    return title, abstract, [a for a in authors if a]


async def _fetch_tweet_fxtwitter(
    tweet_id: str, client: PoliteClient
) -> tuple[str, str, list[str]] | None:
    """Fetch tweet via fxtwitter API (free, no auth required)."""
    try:
        resp = await client.get(f"https://api.fxtwitter.com/status/{tweet_id}")
        data = resp.json()
        tweet = data.get("tweet", {})
        if not tweet:
            return None
        author = tweet.get("author", {}).get("screen_name", "")
        text = str(tweet.get("text", ""))
        title = f"@{author}: {text[:80]}" if author else text[:80]
        return title, text, [author] if author else []
    except Exception:
        return None


async def fetch_tweet(url: str, client: PoliteClient) -> tuple[str, str, list[str]]:
    bearer = None
    try:
        from jarvis.config import get_backend_token

        bearer = get_backend_token("twitter")
    except Exception:
        bearer = None

    match = _TWEET_ID_RE.search(url)
    tweet_id = match.group(1) if match else ""

    # Tier 1: Twitter API v2 (requires bearer token)
    if bearer and tweet_id:
        try:
            resp = await client.get(
                f"https://api.twitter.com/2/tweets/{tweet_id}?tweet.fields=text,author_id,created_at&expansions=author_id&user.fields=name,username",
                headers={"Authorization": f"Bearer {bearer}"},
            )
            data = resp.json()
            tweet = data.get("data", {})
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            user = users.get(tweet.get("author_id", ""), {})
            author = user.get("username") or user.get("name") or ""
            text = str(tweet.get("text", ""))
            title = f"@{author}: {text[:80]}" if author else text[:80]
            return title, text, [author] if author else []
        except Exception:
            pass  # Fall through to fxtwitter

    # Tier 2: fxtwitter API (free, no auth required)
    if tweet_id:
        result = await _fetch_tweet_fxtwitter(tweet_id, client)
        if result:
            return result

    # Tier 3: oEmbed fallback (increasingly unreliable)
    try:
        resp = await client.get(f"https://publish.twitter.com/oembed?url={url}&omit_script=true")
        data = resp.json()
        author = str(data.get("author_name", ""))
        html = str(data.get("html", ""))
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        title = f"{author}: {text[:80]}" if author else text[:80]
        return title, text, [author] if author else []
    except Exception:
        return "", "", []


async def fetch_github(url: str, client: PoliteClient) -> tuple[str, str, list[str]]:
    match = _GITHUB_REPO_RE.search(url)
    if not match:
        return "", "", []
    owner, repo = match.group(1), match.group(2).removesuffix(".git")
    headers = {"Accept": "application/vnd.github+json"}
    try:
        from jarvis.config import get_backend_token

        token = get_backend_token("github")
    except Exception:
        token = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
    data = resp.json()
    readme_preview = ""
    readme_resp = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/readme",
        headers={**headers, "Accept": "application/vnd.github.raw+json"},
    )
    if readme_resp.status_code == 200:
        readme_preview = readme_resp.text[:800]
    title = str(data.get("full_name", f"{owner}/{repo}"))
    description = str(data.get("description", "")).strip()
    lang = str(data.get("language", "")).strip()
    topics = data.get("topics", [])
    topic_text = ", ".join(str(t) for t in topics[:8])
    parts = [
        description,
        f"Language: {lang}" if lang else "",
        f"Topics: {topic_text}" if topic_text else "",
        readme_preview,
    ]
    text = "\n".join(part for part in parts if part)
    return title, text, [owner]


async def fetch_pdf(url: str, client: PoliteClient) -> tuple[str, str, list[str]]:
    resp = await client.get(url)
    pdf_logger = logging.getLogger("pypdf")
    previous_level = pdf_logger.level
    pdf_logger.setLevel(logging.ERROR)
    with contextlib.redirect_stderr(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reader = await _to_thread(PdfReader, io.BytesIO(resp.content))
    pdf_logger.setLevel(previous_level)
    meta = reader.metadata
    title = str((meta.get("/Title") if meta else "") or "").strip()
    text_parts: list[str] = []
    for page in reader.pages[:2]:
        page_text = await _to_thread(page.extract_text)
        if page_text:
            text_parts.append(page_text)
    text = "\n".join(text_parts)[:1500]
    if not title:
        for line in text.splitlines():
            stripped = line.strip()
            if len(stripped) > 10:
                title = stripped[:200]
                break
    return title, text, []


async def fetch_generic(url: str, client: PoliteClient) -> tuple[str, str, list[str]]:
    resp = await client.get(url)
    html = resp.text
    extracted = await _to_thread(
        trafilatura.extract,
        html,
        url=str(resp.url),
        include_comments=False,
        include_tables=False,
        output_format="txt",
        with_metadata=True,
    )
    metadata = await _to_thread(trafilatura.extract_metadata, html, default_url=str(resp.url))
    title = getattr(metadata, "title", "") if metadata else ""
    author = getattr(metadata, "author", "") if metadata else ""
    description = getattr(metadata, "description", "") if metadata else ""
    text = extracted or ""
    if not title or not description:
        soup = await _to_thread(BeautifulSoup, html, "lxml")
        if not title:
            og_title = soup.find("meta", property="og:title")
            title = (
                str(og_title.get("content", ""))
                if og_title
                else (soup.title.string.strip() if soup.title and soup.title.string else "")
            )
        if not description:
            og_desc = soup.find("meta", property="og:description")
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if og_desc and og_desc.get("content"):
                description = str(og_desc["content"])
            elif meta_desc and meta_desc.get("content"):
                description = str(meta_desc["content"])
    body = "\n".join(part for part in [description.strip(), text[:1200].strip()] if part)
    authors = [str(author).strip()] if author else []
    return str(title).strip(), body.strip(), authors


async def fetch_url_content(
    item: ReadingItem,
    client: PoliteClient,
    cache: URLCache,
    no_cache: bool = False,
) -> FetchedContent:
    if not no_cache:
        cached = cache.get(item.url, ttl_days_for_url(item.url))
        if cached is not None:
            return cached

    try:
        if item.item_type.value == "paper" and "arxiv.org" in item.url.lower():
            title, text, authors = await fetch_arxiv(item.url, client)
        elif item.item_type.value == "tweet":
            title, text, authors = await fetch_tweet(item.url, client)
        elif item.item_type.value == "repo":
            title, text, authors = await fetch_github(item.url, client)
        elif item.item_type.value == "pdf":
            title, text, authors = await fetch_pdf(item.url, client)
        else:
            title, text, authors = await fetch_generic(item.url, client)
        result = FetchedContent(
            item=item,
            fetched_title=title or item.title,
            fetched_text=text,
            authors=authors,
            fetch_status="success",
            fetched_at=timestamp_now(),
        )
    except httpx.TimeoutException:
        result = FetchedContent(
            item=item,
            fetched_title=item.title,
            fetched_text=item.description,
            authors=[],
            fetch_status="timeout",
            fetched_at=timestamp_now(),
        )
    except httpx.HTTPStatusError as exc:
        status = "rate_limited" if exc.response.status_code == 429 else "failed"
        result = FetchedContent(
            item=item,
            fetched_title=item.title,
            fetched_text=item.description,
            authors=[],
            fetch_status=status,
            fetched_at=timestamp_now(),
        )
    except Exception:
        result = FetchedContent(
            item=item,
            fetched_title=item.title,
            fetched_text=item.description,
            authors=[],
            fetch_status="failed",
            fetched_at=timestamp_now(),
        )

    cache.set(item.url, result)
    return result


async def fetch_all(items: Sequence[ReadingItem], no_cache: bool = False) -> list[FetchedContent]:
    cache = URLCache()
    client = PoliteClient()
    results: list[FetchedContent] = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        transient=True,
    )
    task_id = progress.add_task("Fetching content", total=len(items))
    try:
        with progress:
            for item in items:
                result = await fetch_url_content(item, client, cache, no_cache=no_cache)
                results.append(result)
                progress.advance(task_id)
    finally:
        await client.aclose()
    return results
