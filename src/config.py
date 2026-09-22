"""환경변수(.env) 로딩 및 공통 설정."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# --- 카카오 ---
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
# REST API 키의 클라이언트 시크릿이 활성화된 경우 토큰 요청 시 필수 (앱>플랫폼 키>REST API 키에서 확인)
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:8000/oauth")
KAKAO_TOKEN_PATH = BASE_DIR / os.getenv("KAKAO_TOKEN_PATH", "tokens/kakao_token.json")

# --- 뉴스 수집 ---
DEFAULT_RSS_URLS = "https://www.hankyung.com/feed/finance,https://www.yna.co.kr/rss/economy.xml"
RSS_URLS = _split_csv(os.getenv("RSS_URLS", DEFAULT_RSS_URLS))
NEWS_COUNT = int(os.getenv("NEWS_COUNT", "5"))
# 제목에 이 키워드 중 하나라도 포함된 뉴스만 발송 (비워두면 전체 발송)
KEYWORDS = _split_csv(os.getenv("KEYWORDS", ""))
# 제목 유사도가 이 값 이상이면 같은 뉴스로 간주해 중복 제거 (0~1)
DEDUP_SIMILARITY = float(os.getenv("DEDUP_SIMILARITY", "0.6"))

# --- 관심종목 시세 ---
# 카테고리별로 묶어서 표시하려면 WATCHLIST_PATH가 가리키는 JSON 파일(기본 watchlist.json)을 사용한다.
# 간단히 한 그룹만 쓰려면 WATCHLIST 환경변수(예: "005930:삼성전자,035420:NAVER")로도 설정 가능.
WATCHLIST_PATH = BASE_DIR / os.getenv("WATCHLIST_PATH", "watchlist.json")
WATCHLIST = _split_csv(os.getenv("WATCHLIST", ""))

# --- 지수 요약 ---
SEND_MARKET_SUMMARY = os.getenv("SEND_MARKET_SUMMARY", "true").lower() == "true"

# --- AI 한줄 요약 (선택, ANTHROPIC_API_KEY 필요) ---
USE_AI_SUMMARY = os.getenv("USE_AI_SUMMARY", "false").lower() == "true"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_SUMMARY_MODEL = os.getenv("AI_SUMMARY_MODEL", "claude-haiku-4-5-20251001")

# --- 카카오 메시지 템플릿 ---
USE_LIST_TEMPLATE = os.getenv("USE_LIST_TEMPLATE", "true").lower() == "true"
LIST_TEMPLATE_MAX_ITEMS = 3  # 카카오 list 템플릿 contents 최대 개수

# --- 재시도 / 로깅 ---
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("RETRY_BACKOFF_SECONDS", "2"))
LOG_PATH = BASE_DIR / os.getenv("LOG_PATH", "logs/app.log")

# --- HTML 리포트 ---
SAVE_HTML_REPORT = os.getenv("SAVE_HTML_REPORT", "true").lower() == "true"
REPORTS_DIR = BASE_DIR / os.getenv("REPORTS_DIR", "reports")

# --- GitHub Pages 배포 (카카오톡 링크 버튼용) ---
# 비워두면 배포를 건너뛴다. 예: https://bbddana.github.io/stock-news-kakao/
PUBLISH_REPORT_URL = os.getenv("PUBLISH_REPORT_URL", "")
