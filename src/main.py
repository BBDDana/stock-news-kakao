"""증권뉴스 + 지수/관심종목 요약을 카카오톡 '나에게 보내기'로 전송하는 진입점.

사용법:
  python -m src.main                # 기본(일반) 브리핑
  python -m src.main --mode open    # 장 시작 전 브리핑
  python -m src.main --mode close   # 장 마감 후 브리핑
"""
import argparse
import sys
from datetime import datetime

from src.ai_summary import fetch_ai_summary
from src.config import SAVE_HTML_REPORT, SEND_MARKET_SUMMARY, USE_LIST_TEMPLATE
from src.html_report import build_html, save_report
from src.kakao_sender import send_news_list, send_text
from src.logger import get_logger
from src.market_index import fetch_market_data, format_market_summary
from src.news_fetcher import NewsItem, fetch_news
from src.watchlist import fetch_watchlist_data, format_watchlist_summary

logger = get_logger()

MODE_LABEL = {
    "open": "장전 브리핑",
    "close": "장마감 브리핑",
    "default": "증권뉴스",
}


def format_text_message(
    mode: str,
    news: list[NewsItem],
    market_summary: str,
    watchlist_summary: str,
    ai_summary: str,
) -> str:
    """헤드라인 없이 지수/관심종목/AI 요약만 있으면 None을 반환해 전송을 건너뛸 수 있게 한다."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    label = MODE_LABEL.get(mode, MODE_LABEL["default"])

    body_parts = []
    if ai_summary:
        body_parts.append(ai_summary)
    if market_summary:
        body_parts.append(market_summary)
    if watchlist_summary:
        body_parts.append(watchlist_summary)

    headline_lines = [f"{i}. {item.title}" for i, item in enumerate(news, start=1)]
    if headline_lines:
        body_parts.append("📰 헤드라인\n" + "\n".join(headline_lines))

    if not body_parts:
        return ""

    divider = "─" * 16
    return f"📌 {label} {today}\n{divider}\n\n" + f"\n\n{divider}\n\n".join(body_parts)


def run(mode: str) -> None:
    news = fetch_news()
    if not news:
        logger.warning("가져온 뉴스가 없어 전송을 건너뜁니다.")
        return

    market_data = fetch_market_data() if SEND_MARKET_SUMMARY else {}
    watchlist_data = fetch_watchlist_data()
    market_summary = format_market_summary(market_data)
    watchlist_summary = format_watchlist_summary(watchlist_data)
    ai_summary = fetch_ai_summary(news)

    label = MODE_LABEL.get(mode, MODE_LABEL["default"])

    if SAVE_HTML_REPORT:
        try:
            html = build_html(
                mode=mode,
                date_str=datetime.now().strftime("%Y-%m-%d %H:%M"),
                news=news,
                market_data=market_data,
                watchlist_data=watchlist_data,
                ai_summary_text=ai_summary,
            )
            report_path = save_report(html, mode)
            logger.info(f"HTML 리포트 저장: {report_path}")
        except Exception:
            logger.exception("HTML 리포트 생성 중 오류가 발생했습니다.")

    if USE_LIST_TEMPLATE:
        send_news_list(header_title=f"📰 {label} · 오늘의 증권뉴스", news=news)
        # 지수/관심종목/AI 요약은 카드형 메시지에 넣을 수 없어 있을 때만 별도 텍스트로 전송
        extra_text = format_text_message(mode, [], market_summary, watchlist_summary, ai_summary)
        if extra_text:
            send_text(extra_text, web_url=news[0].link)
    else:
        message = format_text_message(mode, news, market_summary, watchlist_summary, ai_summary)
        send_text(message, web_url=news[0].link)

    logger.info(f"증권뉴스({label})를 카카오톡으로 전송했습니다. (뉴스 {len(news)}건)")


def main() -> None:
    parser = argparse.ArgumentParser(description="증권뉴스 카카오톡 자동 발송")
    parser.add_argument("--mode", choices=["open", "close", "default"], default="default")
    args = parser.parse_args()

    try:
        run(args.mode)
    except Exception:
        logger.exception("증권뉴스 발송 중 오류가 발생했습니다.")
        sys.exit(1)


if __name__ == "__main__":
    main()
