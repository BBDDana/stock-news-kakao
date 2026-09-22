"""카카오톡 '나에게 보내기' API로 메시지를 전송한다."""
import json

import requests

from src.config import (
    KAKAO_CLIENT_SECRET,
    KAKAO_REST_API_KEY,
    KAKAO_TOKEN_PATH,
    LIST_TEMPLATE_MAX_ITEMS,
)
from src.logger import get_logger
from src.news_fetcher import NewsItem
from src.retry import retry_call

logger = get_logger()

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def _load_token() -> dict:
    if not KAKAO_TOKEN_PATH.exists():
        raise SystemExit(
            "카카오 토큰이 없습니다. 먼저 `python -m src.kakao_auth` 를 실행해 인증하세요."
        )
    return json.loads(KAKAO_TOKEN_PATH.read_text(encoding="utf-8"))


def _save_token(token: dict) -> None:
    KAKAO_TOKEN_PATH.write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding="utf-8")


def _refresh_access_token(token: dict) -> dict:
    """access_token은 6시간, refresh_token은 발급 정책에 따라 만료되므로 전송 전 항상 갱신한다."""
    refresh_data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": token["refresh_token"],
    }
    if KAKAO_CLIENT_SECRET:
        refresh_data["client_secret"] = KAKAO_CLIENT_SECRET

    response = requests.post(TOKEN_URL, data=refresh_data, timeout=10)
    response.raise_for_status()
    refreshed = response.json()

    token["access_token"] = refreshed["access_token"]
    if "refresh_token" in refreshed:  # 카카오가 refresh_token을 재발급하는 경우가 있음
        token["refresh_token"] = refreshed["refresh_token"]
    _save_token(token)
    return token


def _post_template(access_token: str, template_object: dict) -> dict:
    response = requests.post(
        SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=10,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("result_code") != 0:
        raise RuntimeError(f"카카오톡 전송 실패: {result}")
    return result


def _get_access_token() -> str:
    token = retry_call(lambda: _refresh_access_token(_load_token()), label="카카오 토큰 갱신")
    return token["access_token"]


def send_text(text: str, web_url: str | None = None, button_title: str | None = None) -> None:
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": web_url or "https://finance.naver.com",
            "mobile_web_url": web_url or "https://finance.naver.com",
        },
    }
    if button_title:
        template_object["button_title"] = button_title

    access_token = _get_access_token()
    retry_call(lambda: _post_template(access_token, template_object), label="텍스트 메시지 전송")


def send_news_list(header_title: str, news: list[NewsItem]) -> None:
    """카드형(list) 템플릿으로 뉴스를 전송한다. 카카오 list 템플릿은 contents를 최대
    LIST_TEMPLATE_MAX_ITEMS개까지만 지원하므로 초과분은 잘라서 보낸다. 실패 시 텍스트로 대체 전송한다."""
    items = news[:LIST_TEMPLATE_MAX_ITEMS]
    if not items:
        return

    template_object = {
        "object_type": "list",
        "header_title": header_title,
        "header_link": {"web_url": items[0].link, "mobile_web_url": items[0].link},
        "contents": [
            {
                "title": item.title,
                "description": item.source,
                "link": {"web_url": item.link, "mobile_web_url": item.link},
            }
            for item in items
        ],
        "buttons": [
            {
                "title": "기사 보기",
                "link": {"web_url": items[0].link, "mobile_web_url": items[0].link},
            }
        ],
    }

    access_token = _get_access_token()
    try:
        retry_call(lambda: _post_template(access_token, template_object), label="뉴스 카드 메시지 전송")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"list 템플릿 전송 실패, 텍스트로 대체합니다: {exc}")
        fallback_text = header_title + "\n\n" + "\n".join(f"- {i.title}\n  {i.link}" for i in items)
        retry_call(lambda: _post_template(access_token, {
            "object_type": "text",
            "text": fallback_text,
            "link": {"web_url": items[0].link, "mobile_web_url": items[0].link},
        }), label="텍스트 대체 전송")


if __name__ == "__main__":
    send_text("증권뉴스 자동화 테스트 메시지입니다.")
    print("[완료] 카카오톡 '나에게 보내기'로 테스트 메시지를 전송했습니다.")
