#!/usr/bin/env python3
"""Update the static episode markup from The American Over RSS feed."""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo


FEED_URL = "https://feeds.zencastr.com/f/j_3joC2M.rss"
INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
EASTERN = ZoneInfo("America/New_York")


def text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    return (child.text or "").strip() if child is not None else ""


def safe_episode_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"zencastr.com", "www.zencastr.com"}:
        raise ValueError(f"Unexpected episode URL in feed: {value!r}")
    return value


def episode_number(item: ET.Element, title: str) -> int:
    explicit = text(item, f"{ITUNES}episode")
    if explicit.isdigit():
        return int(explicit)
    match = re.match(r"\s*Episode\s+(\d+)\s*[:\-]?\s*", title, re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not find an episode number in {title!r}")
    return int(match.group(1))


def clean_title(title: str) -> str:
    title = re.sub(r"^\s*Episode\s+\d+\s*[:\-]?\s*", "", title, flags=re.IGNORECASE).strip()
    return title.replace("...", "…")


def format_date(value: str, short: bool = False) -> str:
    date = parsedate_to_datetime(value).astimezone(EASTERN)
    month = date.strftime("%b" if short else "%B")
    return f"{month} {date.day}, {date.year}"


def format_duration(value: str) -> str:
    raw = value.strip()
    if raw.isdigit():
        total_seconds = int(raw)
    else:
        parts = [int(part) for part in raw.split(":")]
        if len(parts) == 2:
            total_seconds = parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            total_seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            raise ValueError(f"Unexpected duration: {value!r}")
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def duration_minutes(value: str) -> int:
    raw = value.strip()
    if raw.isdigit():
        seconds = int(raw)
    else:
        parts = [int(part) for part in raw.split(":")]
        seconds = sum(part * factor for part, factor in zip(reversed(parts), (1, 60, 3600)))
    return max(1, round(seconds / 60))


def parse_feed() -> list[dict[str, object]]:
    request = urllib.request.Request(FEED_URL, headers={"User-Agent": "the-american-over-site/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read(2_000_000)
    root = ET.fromstring(payload)
    episodes: list[dict[str, object]] = []
    for item in root.findall("./channel/item")[:100]:
        full_title = text(item, "title")
        duration = text(item, f"{ITUNES}duration")
        episodes.append(
            {
                "number": episode_number(item, full_title),
                "title": clean_title(full_title),
                "url": safe_episode_url(text(item, "link")),
                "published": text(item, "pubDate"),
                "duration": duration,
                "timestamp": parsedate_to_datetime(text(item, "pubDate")).timestamp(),
            }
        )
    if not episodes:
        raise ValueError("The RSS feed did not contain any episodes")
    episodes.sort(key=lambda episode: float(episode["timestamp"]), reverse=True)
    return episodes


def replace_region(document: str, name: str, content: str) -> str:
    start = f"<!-- rss:{name}:start -->"
    end = f"<!-- rss:{name}:end -->"
    pattern = re.compile(
        rf"^(?P<indent>[ \t]*){re.escape(start)}.*?^[ \t]*{re.escape(end)}",
        re.DOTALL | re.MULTILINE,
    )

    def replacement(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return f"{indent}{start}\n{content}\n{indent}{end}"

    updated, count = pattern.subn(replacement, document)
    if count != 1:
        raise ValueError(f"Expected one {name!r} region, found {count}")
    return updated


def render(episodes: list[dict[str, object]]) -> None:
    latest = episodes[0]
    latest_url = html.escape(str(latest["url"]), quote=True)
    latest_title = html.escape(str(latest["title"]), quote=False)
    latest_number = int(latest["number"])

    latest_link = (
        f'            <a class="primary-link" href="{latest_url}" target="_blank" '
        'rel="noreferrer">Listen to the latest episode</a>'
    )
    latest_card = "\n".join(
        [
            '      <section class="latest" aria-labelledby="latest-title">',
            '        <div class="section-heading">',
            '          <p>Latest episode</p>',
            f'          <p>{format_date(str(latest["published"]))} · {duration_minutes(str(latest["duration"]))} min</p>',
            '        </div>',
            '        <div class="latest-body">',
            f'          <p class="episode-no">Episode {latest_number}</p>',
            f'          <h2 id="latest-title">{latest_title}</h2>',
            f'          <a class="primary-link light" href="{latest_url}" target="_blank" rel="noreferrer">Play episode</a>',
            '        </div>',
            '      </section>',
        ]
    )

    rows = []
    for episode in episodes:
        url = html.escape(str(episode["url"]), quote=True)
        title = html.escape(str(episode["title"]), quote=False)
        number = int(episode["number"])
        date = format_date(str(episode["published"]), short=True)
        duration = format_duration(str(episode["duration"]))
        rows.append(
            f'          <li><a href="{url}" target="_blank" rel="noreferrer">'
            f'<span class="episode-number">{number:02d}</span>'
            f'<span class="episode-title">{title}</span>'
            f'<span class="episode-date">{date}</span>'
            f'<span class="episode-length">{duration}</span></a></li>'
        )
    episode_list = "\n".join(['        <ol class="episode-list">', *rows, '        </ol>'])

    document = INDEX_PATH.read_text(encoding="utf-8")
    document = replace_region(document, "latest-link", latest_link)
    document = replace_region(document, "latest-card", latest_card)
    document = replace_region(document, "episode-list", episode_list)
    INDEX_PATH.write_text(document, encoding="utf-8")


if __name__ == "__main__":
    render(parse_feed())
