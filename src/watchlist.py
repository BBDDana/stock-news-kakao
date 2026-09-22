"""관심종목 현재가를 가져온다.

우선순위:
1. WATCHLIST_PATH(기본 watchlist.json)가 존재하면 카테고리별 그룹으로 표시
   형식: {"그룹명": [{"code": "005930", "name": "삼성전자"}, ...], ...}
2. 없으면 WATCHLIST 환경변수(예: "005930:삼성전자,035420:NAVER")를 단일 그룹으로 표시
"""
import json

import requests

from src.config import WATCHLIST, WATCHLIST_PATH
from src.format_utils import format_change
from src.market_index import Quote
from src.retry import retry_call

STOCK_URL = "https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _load_groups() -> dict[str, list[dict[str, str]]]:
    if WATCHLIST_PATH.exists():
        return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))

    if WATCHLIST:
        items = []
        for entry in WATCHLIST:
            code, _, name = entry.partition(":")
            items.append({"code": code.strip(), "name": (name or code).strip()})
        return {"관심종목": items}

    return {}


def _fetch_one(code: str, display_name: str) -> Quote | None:
    data = requests.get(STOCK_URL.format(code=code), headers=HEADERS, timeout=10).json()
    datas = data.get("datas") or []
    if not datas:
        return None
    d = datas[0]
    return Quote(display_name, f"{d['closePrice']}원", d["fluctuationsRatio"])


def fetch_watchlist_data() -> dict[str, list[Quote]]:
    groups = _load_groups()
    if not groups:
        return {}

    result: dict[str, list[Quote]] = {}
    for group_name, stocks in groups.items():
        quotes = []
        for stock in stocks:
            code, name = stock["code"], stock["name"]
            try:
                quote = retry_call(lambda c=code, n=name: _fetch_one(c, n), label=f"관심종목 조회({name})")
                if quote:
                    quotes.append(quote)
            except Exception:
                continue
        if quotes:
            result[group_name] = quotes
    return result


def format_watchlist_summary(groups: dict[str, list[Quote]]) -> str:
    if not groups:
        return ""

    sections = []
    for group_name, quotes in groups.items():
        lines = [f"{q.name}  {q.price}  {format_change(q.ratio)}" for q in quotes]
        sections.append(f"🔹 {group_name}\n" + "\n".join(lines))

    return "💼 관심종목\n\n" + "\n\n".join(sections)


def fetch_watchlist_summary() -> str:
    return format_watchlist_summary(fetch_watchlist_data())


if __name__ == "__main__":
    print(fetch_watchlist_summary())
