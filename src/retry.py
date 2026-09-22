"""네트워크 호출 재시도 유틸리티."""
import time
from typing import Callable, TypeVar

from src.config import MAX_RETRIES, RETRY_BACKOFF_SECONDS
from src.logger import get_logger

logger = get_logger()

T = TypeVar("T")


def retry_call(func: Callable[[], T], label: str) -> T:
    """func()를 실행하고 실패 시 지수 백오프로 재시도한다. 모두 실패하면 마지막 예외를 올린다."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001 - 외부 API 호출이라 광범위하게 잡음
            last_error = exc
            logger.warning(f"[재시도 {attempt}/{MAX_RETRIES}] {label} 실패: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    assert last_error is not None
    raise last_error
