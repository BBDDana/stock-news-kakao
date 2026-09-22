"""코스피/코스닥/미국 3대 지수/환율 요약을 가져온다."""
from dataclasses import dataclass

import requests

from src.format_utils import format_change
from src.retry import retry_call

DOMESTIC_URL = "https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI,KOSDAQ"
WORLD_URL = "https://polling.finance.naver.com/api/realtime/worldstock/index/.DJI,.IXIC,.INX"
FX_URL = "https://open.er-api.com/v6/latest/USD"

WORLD_NAME_MAP = {".DJI": "다우", ".IXIC": "나스닥", ".INX": "S&P500"}

HEADERS = {"User-Agent": "Mozilla/5.0"}


@dataclass
class Quote:
    name: str
    price: str
    ratio: str  # 예: "1.65" 또는 "-0.18" (부호는 음수만 포함)


def _fetch_domestic() -> list[Quote]:
    data = requests.get(DOMESTIC_URL, headers=HEADERS, timeout=10).json()["datas"]
    return [Quote(d["stockName"], d["closePrice"], d["fluctuationsRatio"]) for d in data]


def _fetch_world() -> list[Quote]:
    data = requests.get(WORLD_URL, headers=HEADERS, timeout=10).json()["datas"]
    return [
        Quote(WORLD_NAME_MAP.get(d["reutersCode"], d["indexName"]), d["closePrice"], d["fluctuationsRatio"])
        for d in data
    ]


def _fetch_fx() -> Quote | None:
    data = requests.get(FX_URL, timeout=10).json()
    rate = data.get("rates", {}).get("KRW")
    if rate is None:
        return None
    return Quote("USD/KRW", f"{rate:,.2f}원", "0")


def fetch_market_data() -> dict[str, list[Quote]]:
    """실패한 섹션은 빈 리스트로 건너뛰고, 가져온 섹션만 담아 반환한다."""
    sections: dict[str, list[Quote]] = {}

    try:
        domestic = retry_call(_fetch_domestic, label="국내 지수 조회")
        if domestic:
            sections["국내"] = domestic
    except Exception:
        pass

    try:
        world = retry_call(_fetch_world, label="해외 지수 조회")
        if world:
            sections["해외"] = world
    except Exception:
        pass

    try:
        fx = retry_call(_fetch_fx, label="환율 조회")
        if fx:
            sections["환율"] = [fx]
    except Exception:
        pass

    return sections


def format_market_summary(sections: dict[str, list[Quote]]) -> str:
    if not sections:
        return ""

    parts = []
    for name, quotes in sections.items():
        if name == "환율":
            lines = [f"{q.name}  {q.price}" for q in quotes]
        else:
            lines = [f"{q.name}  {q.price}  {format_change(q.ratio)}" for q in quotes]
        parts.append(f"🔹 {name}\n" + "\n".join(lines))

    return "📊 시장 지표\n\n" + "\n\n".join(parts)


def fetch_market_summary() -> str:
    return format_market_summary(fetch_market_data())


if __name__ == "__main__":
    print(fetch_market_summary())
