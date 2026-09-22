"""카카오톡 텍스트 메시지의 가독성을 높이기 위한 등락 표시 유틸리티."""


def change_emoji(ratio: str) -> str:
    try:
        value = float(ratio)
    except ValueError:
        return "▪️"
    if value > 0:
        return "🔺"
    if value < 0:
        return "🔻"
    return "▪️"


def format_change(ratio: str) -> str:
    sign = "+" if not ratio.startswith("-") else ""
    return f"{change_emoji(ratio)} {sign}{ratio}%"
