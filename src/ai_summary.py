"""선택 기능: 오늘의 뉴스 제목들을 한두 문장으로 요약 (ANTHROPIC_API_KEY 필요, requirements-ai.txt 설치 필요)."""
from src.config import AI_SUMMARY_MODEL, ANTHROPIC_API_KEY, USE_AI_SUMMARY
from src.logger import get_logger
from src.news_fetcher import NewsItem

logger = get_logger()


def fetch_ai_summary(news: list[NewsItem]) -> str:
    if not USE_AI_SUMMARY:
        return ""
    if not ANTHROPIC_API_KEY:
        logger.warning("USE_AI_SUMMARY=true 이지만 ANTHROPIC_API_KEY가 없어 AI 요약을 건너뜁니다.")
        return ""

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic 패키지가 없어 AI 요약을 건너뜁니다. `pip install -r requirements-ai.txt` 실행하세요.")
        return ""

    titles = "\n".join(f"- {n.title}" for n in news)
    prompt = (
        "다음은 오늘의 증권 뉴스 제목 목록이다. 전체 흐름을 한국어 2문장 이내로 "
        f"간결하게 요약해줘. 과장하지 말고 사실 위주로.\n\n{titles}"
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=AI_SUMMARY_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return f"[오늘의 요약]\n{text}" if text else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"AI 요약 생성 실패: {exc}")
        return ""
