"""Shared helpers for insurer-specific invoice parsers."""

from __future__ import annotations

import re
from datetime import datetime


def clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = re.sub(r"\s+\d{1,2}:\d{2}", "", str(value).strip())
    cleaned = re.sub(r"[.\-]", "/", cleaned)

    for fmt in (
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%d-%b-%Y",
        "%d-%B-%Y",
    ):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return cleaned


def clean_amount(value) -> float | None:
    if value is None:
        return None

    try:
        text = str(value).replace(",", "").replace("(", "-").replace(")", "").strip()
        if text.startswith("."):
            text = f"0{text}"
        return float(text)
    except (TypeError, ValueError):
        return None


def is_amount(line: str) -> bool:
    return bool(re.fullmatch(r"[\d,]+\.\d{2}", line.strip()))


def get_value_after_label(
    lines: list[str],
    label: str,
    lookahead: int = 4,
) -> str | None:
    """Return the value on the same line as label or the next non-empty line."""
    label_lower = label.lower()

    for index, line in enumerate(lines):
        if label_lower not in line.lower():
            continue

        if ":" in line:
            value = line.split(":", 1)[1].strip()
            if value:
                return value

        for next_line in lines[index + 1 : index + 1 + lookahead]:
            cleaned = next_line.replace(":", "").strip()
            if cleaned:
                return cleaned

    return None
