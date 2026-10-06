"""Shared visual theme for both MU report locales."""

from __future__ import annotations

COLORS = {
    "ink": "#17212B",
    "primary": "#164E87",
    "blue_mid": "#5C91C4",
    "blue_pale": "#DCE9F5",
    "gray_dark": "#52606D",
    "gray_mid": "#B8C2CC",
    "gray_pale": "#F1F4F7",
    "warning": "#9A5B13",
    "paper": "#FFFFFF",
}

FONT_STACK = "'Noto Sans KR','Noto Sans CJK KR',sans-serif"


def contrast_ratio(foreground: str, background: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
