"""여러 RSS 소스에서 증권 뉴스를 모아 중복 제거 후 반환한다. KEYWORDS에 걸리는 뉴스는 상단에 우선 배치된다."""
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime

import requests

from src.config import DEDUP_SIMILARITY, KEYWORDS, NEWS_COUNT, RSS_URLS
from src.logger import get_logger
from src.retry import retry_call

logger = get_logger()


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: object = None  # datetime | None


def _fetch_one(url: str) -> list[NewsItem]:
    response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    root = ET.fromstring(response.content)
    source = (root.findtext("./channel/title") or url).strip()

    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        try:
            published = parsedate_to_datetime(pub_date_raw) if pub_date_raw else None
        except (TypeError, ValueError):
            published = None
        if title and link:
            items.append(NewsItem(title=title, link=link, source=source, published=published))
    return items


def _is_similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a, b).ratio() >= DEDUP_SIMILARITY


def _dedup(items: list[NewsItem]) -> list[NewsItem]:
    unique: list[NewsItem] = []
    for item in items:
        if not any(_is_similar(item.title, kept.title) for kept in unique):
            unique.append(item)
    return unique


def _is_priority(item: NewsItem) -> bool:
    return any(keyword in item.title for keyword in KEYWORDS)


def _prioritize(items: list[NewsItem], count: int) -> list[NewsItem]:
    """KEYWORDS에 걸리는 뉴스를 상단으로 올리되, 최소 절반은 일반 뉴스로 채워 전체 뉴스 흐름도 유지한다."""
    if not KEYWORDS:
        return items[:count]

    priority = [i for i in items if _is_priority(i)]
    rest = [i for i in items if not _is_priority(i)]

    priority_slots = max(1, count // 2)
    chosen_priority = priority[:priority_slots]
    chosen_rest = rest[: count - len(chosen_priority)]
    return chosen_priority + chosen_rest


def fetch_news(count: int = NEWS_COUNT) -> list[NewsItem]:
    all_items: list[NewsItem] = []
    for url in RSS_URLS:
        try:
            all_items.extend(retry_call(lambda u=url: _fetch_one(u), label=f"RSS 수집({url})"))
        except Exception as exc:  # noqa: BLE001
            logger.error(f"RSS 소스를 건너뜁니다: {url} ({exc})")

    all_items.sort(key=lambda i: i.published.timestamp() if i.published else 0.0, reverse=True)
    deduped = _dedup(all_items)
    return _prioritize(deduped, count)


if __name__ == "__main__":
    for n in fetch_news():
        print(f"- [{n.source}] {n.title}\n  {n.link}")
