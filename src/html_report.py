"""시장 지표/관심종목/뉴스를 표와 색상을 갖춘 HTML 리포트로 렌더링한다."""
from datetime import datetime
from html import escape
from pathlib import Path

from src.config import REPORTS_DIR
from src.market_index import Quote
from src.news_fetcher import NewsItem

MODE_LABEL = {"open": "장전 브리핑", "close": "장마감 브리핑", "default": "브리핑"}


def _change_class(ratio: str) -> str:
    try:
        value = float(ratio)
    except ValueError:
        return "flat"
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def _change_badge(ratio: str) -> str:
    cls = _change_class(ratio)
    arrow = {"up": "▲", "down": "▼", "flat": "–"}[cls]
    sign = "+" if cls == "up" else ""
    return f'<span class="chg {cls}">{arrow} {sign}{escape(ratio)}%</span>'

def _quote_rows(quotes: list[Quote], with_change: bool = True) -> str:
    rows = []
    for q in quotes:
        change_cell = f"<td class='num'>{_change_badge(q.ratio)}</td>" if with_change else ""
        rows.append(
            f"<tr><td class='name'>{escape(q.name)}</td>"
            f"<td class='num tnum'>{escape(q.price)}</td>{change_cell}</tr>"
        )
    return "\n".join(rows)


def _market_section(market_data: dict[str, list[Quote]]) -> str:
    if not market_data:
        return ""
    blocks = []
    for group_name, quotes in market_data.items():
        with_change = group_name != "환율"
        header_cols = "<th>지표</th><th class='num'>현재가</th>" + ("<th class='num'>등락률</th>" if with_change else "")
        blocks.append(f"""
        <div class="subgroup">
          <h3>{escape(group_name)}</h3>
          <table>
            <thead><tr>{header_cols}</tr></thead>
            <tbody>{_quote_rows(quotes, with_change)}</tbody>
          </table>
        </div>""")
    return f"""
    <section class="card">
      <p class="eyebrow">Market</p>
      <h2>시장 지표</h2>
      <div class="subgroups">{"".join(blocks)}</div>
    </section>"""


def _watchlist_section(watchlist_data: dict[str, list[Quote]]) -> str:
    if not watchlist_data:
        return ""
    blocks = []
    for group_name, quotes in watchlist_data.items():
        blocks.append(f"""
        <div class="subgroup">
          <h3>{escape(group_name)}</h3>
          <table>
            <thead><tr><th>종목</th><th class="num">현재가</th><th class="num">등락률</th></tr></thead>
            <tbody>{_quote_rows(quotes)}</tbody>
          </table>
        </div>""")
    return f"""
    <section class="card">
      <p class="eyebrow">Watchlist</p>
      <h2>관심종목</h2>
      <div class="subgroups">{"".join(blocks)}</div>
    </section>"""


def _news_section(news: list[NewsItem]) -> str:
    if not news:
        return ""
    items = "\n".join(
        f"""<li>
              <a href="{escape(item.link)}" target="_blank" rel="noopener">
                <span class="idx">{i:02d}</span>
                <span class="headline-text">{escape(item.title)}</span>
                <span class="source">{escape(item.source)}</span>
              </a>
            </li>"""
        for i, item in enumerate(news, start=1)
    )
    return f"""
    <section class="card">
      <p class="eyebrow">Headlines</p>
      <h2>오늘의 헤드라인</h2>
      <ol class="headlines">{items}</ol>
    </section>"""


def _ai_section(ai_summary_text: str) -> str:
    if not ai_summary_text:
        return ""
    body = ai_summary_text.split("\n", 1)[-1] if ai_summary_text.startswith("[") else ai_summary_text
    return f"""
    <section class="card ai">
      <p class="eyebrow">Summary</p>
      <h2>오늘의 요약</h2>
      <p class="ai-text">{escape(body)}</p>
    </section>"""


def build_html(
    mode: str,
    date_str: str,
    news: list[NewsItem],
    market_data: dict[str, list[Quote]],
    watchlist_data: dict[str, list[Quote]],
    ai_summary_text: str = "",
) -> str:
    label = MODE_LABEL.get(mode, MODE_LABEL["default"])
    sections = (
        _ai_section(ai_summary_text)
        + _market_section(market_data)
        + _watchlist_section(watchlist_data)
        + _news_section(news)
    )

    return f"""<title>증권기자 브리프</title>
<style>
:root {{
  --paper: #f6f3ec;
  --surface: #ffffff;
  --ink: #211f1c;
  --muted: #6b6459;
  --line: #e4dfd3;
  --accent: #b8862f;
  --accent-deep: #1d2a44;
  --up: #c0392b;
  --up-bg: #fbeae7;
  --down: #2a5ca8;
  --down-bg: #e9f0fa;
  --flat: #8a8578;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper: #15130f;
    --surface: #1e1b16;
    --ink: #ede8dd;
    --muted: #a79e8d;
    --line: #332e25;
    --accent: #d9ae5c;
    --accent-deep: #cddcfb;
    --up: #e5695c;
    --up-bg: #3a211d;
    --down: #7fb0e8;
    --down-bg: #1d2b3f;
    --flat: #93897a;
  }}
}}
:root[data-theme="dark"] {{
  --paper: #15130f;
  --surface: #1e1b16;
  --ink: #ede8dd;
  --muted: #a79e8d;
  --line: #332e25;
  --accent: #d9ae5c;
  --accent-deep: #cddcfb;
  --up: #e5695c;
  --up-bg: #3a211d;
  --down: #7fb0e8;
  --down-bg: #1d2b3f;
  --flat: #93897a;
}}

* {{ box-sizing: border-box; }}
body {{
  background: var(--paper);
  color: var(--ink);
  font-family: 'IBM Plex Sans KR', 'Noto Sans KR', -apple-system, sans-serif;
  padding: 0 16px;
  padding-block: 28px 56px;
  max-width: 720px;
  margin: 0 auto;
}}
h1, h2, h3 {{ font-family: 'Gowun Dodum', 'Noto Sans KR', sans-serif; margin: 0; }}
.tnum {{ font-variant-numeric: tabular-nums; }}

.masthead {{
  background: var(--accent-deep);
  color: #f4efe3;
  border-radius: 14px;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 24px;
}}
.masthead .brand {{
  font-family: 'Gowun Dodum', sans-serif;
  font-size: 1.5rem;
  letter-spacing: 0.02em;
}}
.masthead .meta {{
  color: var(--accent);
  font-size: 0.9rem;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}}
.masthead .pill {{
  border: 1px solid var(--accent);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 0.8rem;
}}

.card {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 18px;
}}
.eyebrow {{
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 4px;
  font-weight: 600;
}}
.card h2 {{ font-size: 1.25rem; margin-bottom: 14px; }}

.ai-text {{ color: var(--ink); line-height: 1.65; margin: 0; }}

.subgroups {{ display: flex; flex-direction: column; gap: 18px; }}
.subgroup h3 {{
  font-size: 0.95rem;
  color: var(--muted);
  font-weight: 500;
  margin-bottom: 8px;
}}
table {{ width: 100%; border-collapse: collapse; }}
thead th {{
  text-align: left;
  font-size: 0.72rem;
  color: var(--muted);
  font-weight: 500;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--line);
}}
th.num, td.num {{ text-align: right; white-space: nowrap; padding-left: 10px; }}
td.name {{ width: 100%; }}
tbody td {{
  padding-top: 9px;
  padding-bottom: 9px;
  border-bottom: 1px solid var(--line);
  font-size: 0.95rem;
  vertical-align: middle;
}}
tbody tr:last-child td {{ border-bottom: none; }}
td.name {{ color: var(--ink); overflow-wrap: break-word; }}

.chg {{
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
  white-space: nowrap;
}}
.chg.up {{ color: var(--up); background: var(--up-bg); }}
.chg.down {{ color: var(--down); background: var(--down-bg); }}
.chg.flat {{ color: var(--flat); background: transparent; }}

.headlines {{
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}}
.headlines li {{ border-bottom: 1px solid var(--line); }}
.headlines li:last-child {{ border-bottom: none; }}
.headlines a {{
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 12px 0;
  text-decoration: none;
  color: inherit;
}}
.headlines .idx {{
  font-family: 'Gowun Dodum', sans-serif;
  color: var(--accent);
  font-size: 0.85rem;
  flex: none;
}}
.headlines .headline-text {{ flex: 1; line-height: 1.5; }}
.headlines a:hover .headline-text {{ text-decoration: underline; }}
.headlines .source {{
  flex: none;
  font-size: 0.75rem;
  color: var(--muted);
  white-space: nowrap;
}}

footer {{
  text-align: center;
  color: var(--muted);
  font-size: 0.78rem;
  margin-top: 28px;
}}

@media (max-width: 480px) {{
  .headlines .source {{ display: none; }}
}}
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap">

<div class="masthead">
  <div class="brand">증권기자</div>
  <div class="meta">
    <span class="pill">{escape(label)}</span>
    <span>{escape(date_str)}</span>
  </div>
</div>

{sections}

<footer>매일 자동 수집 · 한국경제 · 연합뉴스 · 네이버금융</footer>
"""


def save_report(html: str, mode: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = REPORTS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_{mode}.html"
    dated_path.write_text(html, encoding="utf-8")
    (REPORTS_DIR / "latest.html").write_text(html, encoding="utf-8")
    return dated_path


if __name__ == "__main__":
    from datetime import datetime

    from src.market_index import fetch_market_data
    from src.news_fetcher import fetch_news
    from src.watchlist import fetch_watchlist_data

    html = build_html(
        mode="open",
        date_str=datetime.now().strftime("%Y-%m-%d %H:%M"),
        news=fetch_news(),
        market_data=fetch_market_data(),
        watchlist_data=fetch_watchlist_data(),
    )
    print(html[:500])
