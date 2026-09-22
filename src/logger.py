"""콘솔 + 파일 로깅 설정. 작업 스케줄러로 무인 실행될 때 실패 원인을 남기기 위함."""
import logging
from logging.handlers import RotatingFileHandler

from src.config import LOG_PATH


def get_logger(name: str = "stock_news") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:  # 중복 설정 방지
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
