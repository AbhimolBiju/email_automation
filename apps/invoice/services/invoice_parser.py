"""Optional label-based enrichment from invoice OCR text content."""

from __future__ import annotations

import re
from typing import Any

from documents.ocr_parser import extract_dates, extract_labeled_value, normalize_space

BRANCH_LABELS = ("branch",)
PERIOD_LABELS = ("period",)
POLICY_TYPE_LABELS = ("policy type",)
INSURER_LABELS = ("insurer name", "insurance company", "insurer")

_INVOICE_NO_PATTERNS = (
    re.compile(r"(?i)invoice\s*(?:no|number|#)\s*[:\-]?\s*([A-Z0-9\-/]+)"),
    re.compile(r"(?i)tax\s*invoice\s*(?:no|#)\s*[:\-]?\s*([A-Z0-9\-/]+)"),
)
_PURCHASE_ORDER_PATTERN = re.compile(
    r"(?i)(?:purchase\s*order|p\.?o\.?)\s*(?:no|number|#)?\s*[:\-]?\s*([A-Z0-9\-/]+)"
)
_AMOUNT_PATTERN = re.compile(
    r"(?:AED|USD|DHS)?\s*"
    r"([\d]{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})?|\d+\.\d{1,2})",
    re.IGNORECASE,
)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _lines(text: str) -> list[str]:
    return [normalize_space(line) for line in text.splitlines() if normalize_space(line)]


_KNOWN_LABEL_LINE_RE = re.compile(
    r"(?i)^(branch|policy\s*type|period|total|insurer|invoice|premium)\b"
)


def _looks_like_label_line(line: str) -> bool:
    """Return True when OCR text is another field label, not a field value."""
    stripped = normalize_space(line)
    if not stripped:
        return True
    if _KNOWN_LABEL_LINE_RE.match(stripped):
        return True
    letters = re.sub(r"[^A-Za-z]", "", stripped)
    if letters and letters.isupper() and len(stripped.split()) <= 4:
        return True
    return False


def _extract_inline_label_value(text: str, label_pattern: re.Pattern[str]) -> str:
    """Read ``LABEL: value`` from a single OCR line."""
    for line in _lines(text):
        match = label_pattern.search(line)
        if not match:
            continue
        value = _normalize_text(match.group(1))
        if value and not _looks_like_label_line(value):
            return value
    return ""


def _find_label_anchor_word(
    words: list[dict[str, Any]],
    *,
    single_word_pattern: re.Pattern[str] | None = None,
    multi_word_parts: tuple[str, ...] | None = None,
) -> dict[str, Any] | None:
    """Locate the last word of a label token sequence in OCR word geometry."""
    if single_word_pattern is not None:
        matches = [
            word
            for word in words
            if single_word_pattern.search(str(word.get("content") or ""))
        ]
        if matches:
            return max(
                matches,
                key=lambda word: float((word.get("box") or {}).get("y_center", 0)),
            )

    if multi_word_parts:
        normalized_parts = [part.lower() for part in multi_word_parts]
        for index, word in enumerate(words):
            content = str(word.get("content") or "").strip().lower()
            if content != normalized_parts[0]:
                continue
            if len(normalized_parts) == 1:
                return word
            if index + 1 >= len(words):
                continue
            next_content = str(words[index + 1].get("content") or "").strip().lower()
            if next_content == normalized_parts[1]:
                return words[index + 1]
    return None


def _extract_value_beside_label_from_layout(
    layout: dict[str, Any] | None,
    *,
    label_word_pattern: re.Pattern[str] | None = None,
    label_word_parts: tuple[str, ...] | None = None,
    inline_pattern: re.Pattern[str],
) -> str:
    """Read the table cell to the right of a label using Azure word/line geometry."""
    if not layout:
        return ""

    for line in layout.get("lines") or []:
        content = str(line.get("content") or "")
        match = inline_pattern.search(content)
        if match:
            value = _normalize_text(match.group(1))
            if value and not _looks_like_label_line(value):
                return value

    words: list[dict[str, Any]] = list(layout.get("words") or [])
    if not words:
        return ""

    anchor = _find_label_anchor_word(
        words,
        single_word_pattern=label_word_pattern,
        multi_word_parts=label_word_parts,
    )
    if anchor is None:
        return ""
    anchor_box = anchor.get("box") or {}
    y_center = float(anchor_box.get("y_center", 0))
    y_tol = max(float(anchor_box.get("height", 12)) * 0.85, 12.0)
    x_after_label = float(anchor_box.get("x_max", 0))

    row_tokens: list[tuple[float, str]] = []
    for word in words:
        word_box = word.get("box")
        if not word_box:
            continue
        if abs(float(word_box.get("y_center", 0)) - y_center) > y_tol:
            continue
        if float(word_box.get("x_min", 0)) < x_after_label - 6:
            continue
        content = normalize_space(str(word.get("content") or ""))
        if not content:
            continue
        if label_word_pattern and label_word_pattern.fullmatch(content):
            continue
        if label_word_parts and content.lower() in label_word_parts:
            continue
        if _looks_like_label_line(content):
            continue
        row_tokens.append((float(word_box.get("x_center", 0)), content))

    if not row_tokens:
        return ""

    row_tokens.sort(key=lambda item: item[0])
    return normalize_space(" ".join(token for _, token in row_tokens))


def _extract_label_value_from_text(
    text: str,
    *,
    aliases: tuple[str, ...],
    inline_pattern: re.Pattern[str],
) -> str:
    """Extract a labeled field from OCR text (inline, next-line, or labeled-value helper)."""
    inline_value = _extract_inline_label_value(text, inline_pattern)
    if inline_value:
        return inline_value

    lines = _lines(text)
    labeled = extract_labeled_value(lines, aliases)
    if labeled and not _looks_like_label_line(labeled):
        return labeled

    for index, line in enumerate(lines):
        lowered = line.lower()
        if not any(alias in lowered for alias in aliases):
            continue
        if index + 1 >= len(lines):
            continue
        next_line = lines[index + 1]
        if next_line and not _looks_like_label_line(next_line):
            return next_line
    return ""


def _normalize_amount(value: str) -> str:
    """Strip grouping separators and currency symbols from a numeric token."""
    cleaned = re.sub(r"[^\d.]", "", value.replace(",", ""))
    return cleaned


def _amounts_on_line(line: str) -> list[str]:
    """Return normalized amount strings found on a line (left-to-right)."""
    amounts: list[str] = []
    for match in _AMOUNT_PATTERN.finditer(line):
        token = _normalize_amount(match.group(1))
        if token:
            amounts.append(token)
    return amounts


def _is_subtotal_line(line: str) -> bool:
    lowered = re.sub(r"\s+", "", line.lower())
    return "subtotal" in lowered


def _is_total_label_line(line: str) -> bool:
    """True when the line is a TOTAL row (not SUB TOTAL)."""
    if _is_subtotal_line(line):
        return False
    return bool(re.search(r"(?i)(?:^|[^\w])total(?:[^\w]|$)", line))


def extract_total_premium(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
    layout: dict[str, Any] | None = None,
) -> str:
    """Extract premium from debit note TOTAL row (table bottom-right when possible)."""
    layout_amount = _extract_total_from_layout(layout)
    if layout_amount:
        return layout_amount

    for line in reversed(_lines(text)):
        if not _is_total_label_line(line):
            continue
        amounts = _amounts_on_line(line)
        if amounts:
            return amounts[-1]

    for line in reversed(_lines(text)):
        if not re.search(r"(?i)\btotal\b", line) or _is_subtotal_line(line):
            continue
        amounts = _amounts_on_line(line)
        if amounts:
            return amounts[-1]

    labeled = extract_labeled_value(_lines(text), ("total",))
    if labeled and not _is_subtotal_line(labeled):
        amounts = _amounts_on_line(labeled)
        if amounts:
            return amounts[-1]
        amount_only = _normalize_amount(labeled)
        if amount_only:
            return amount_only

    if existing_fields:
        for key in (
            "total_amount",
            "premium_amount",
            "InvoiceTotal",
            "total",
            "amount_due",
        ):
            value = existing_fields.get(key)
            if value not in (None, ""):
                return _normalize_amount(str(value))
    return ""


def _extract_total_from_layout(layout: dict[str, Any] | None) -> str:
    """Use Azure word/line geometry to read the amount at the bottom-right TOTAL cell."""
    if not layout:
        return ""

    lines: list[dict[str, Any]] = list(layout.get("lines") or [])
    words: list[dict[str, Any]] = list(layout.get("words") or [])
    if not lines and not words:
        return ""

    for line in reversed(lines):
        content = str(line.get("content") or "")
        if not _is_total_label_line(content):
            continue
        amounts = _amounts_on_line(content)
        if amounts:
            return amounts[-1]

        line_box = line.get("box")
        if not line_box:
            continue
        y_center = float(line_box.get("y_center", 0))
        y_tol = max(float(line_box.get("height", 12)) * 0.75, 10.0)
        x_after_label = float(line_box.get("x_max", 0))

        row_amounts: list[tuple[float, str]] = []
        for word in words:
            word_box = word.get("box")
            if not word_box:
                continue
            if abs(float(word_box.get("y_center", 0)) - y_center) > y_tol:
                continue
            if float(word_box.get("x_min", 0)) < x_after_label - 4:
                continue
            for amount in _amounts_on_line(str(word.get("content") or "")):
                row_amounts.append((float(word_box.get("x_center", 0)), amount))

        if row_amounts:
            row_amounts.sort(key=lambda item: item[0])
            return row_amounts[-1][1]

    total_words = [
        word
        for word in words
        if re.fullmatch(r"total", str(word.get("content") or "").strip(), flags=re.IGNORECASE)
    ]
    if not total_words:
        return ""

    anchor = max(
        total_words,
        key=lambda word: float((word.get("box") or {}).get("y_center", 0)),
    )
    anchor_box = anchor.get("box") or {}
    y_center = float(anchor_box.get("y_center", 0))
    y_tol = max(float(anchor_box.get("height", 12)) * 0.75, 10.0)
    x_after_label = float(anchor_box.get("x_max", 0))

    row_amounts = []
    for word in words:
        word_box = word.get("box")
        if not word_box:
            continue
        if abs(float(word_box.get("y_center", 0)) - y_center) > y_tol:
            continue
        if float(word_box.get("x_min", 0)) < x_after_label - 4:
            continue
        for amount in _amounts_on_line(str(word.get("content") or "")):
            row_amounts.append((float(word_box.get("x_center", 0)), amount))

    if not row_amounts:
        return ""

    row_amounts.sort(key=lambda item: item[0])
    return row_amounts[-1][1]


def extract_invoice_number(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str:
    """Extract an invoice number from OCR content when Azure did not return one."""
    if existing_fields:
        for key in ("InvoiceId", "invoice_no"):
            value = existing_fields.get(key)
            if value:
                return _normalize_text(str(value))

    for pattern in _INVOICE_NO_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return ""


def extract_branch(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
    layout: dict[str, Any] | None = None,
) -> str:
    """Extract branch name from a ``BRANCH`` label on debit note documents."""
    layout_value = _extract_value_beside_label_from_layout(
        layout,
        label_word_pattern=re.compile(r"(?i)^branch$"),
        inline_pattern=re.compile(r"(?i)\bbranch\s*[:\-]?\s*(.+)$"),
    )
    if layout_value:
        return layout_value

    text_value = _extract_label_value_from_text(
        text,
        aliases=BRANCH_LABELS,
        inline_pattern=re.compile(r"(?i)\bbranch\s*[:\-]?\s*(.+)$"),
    )
    if text_value:
        return text_value

    if existing_fields:
        for key in ("branch", "Branch"):
            value = existing_fields.get(key)
            if value:
                return _normalize_text(str(value))
    return ""


def extract_policy_period(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Extract policy start/end dates from a ``PERIOD`` label on credit note documents."""
    period_text = ""
    if existing_fields:
        for key in ("period", "Period", "policy_period"):
            value = existing_fields.get(key)
            if value:
                period_text = _normalize_text(str(value))
                break

    if not period_text:
        labeled = extract_labeled_value(_lines(text), PERIOD_LABELS)
        if labeled:
            period_text = labeled

    if not period_text:
        for line in _lines(text):
            match = re.search(r"(?i)\bperiod\b\s*[:\-]?\s*(.+)$", line)
            if match:
                period_text = _normalize_text(match.group(1))
                break

    if not period_text:
        return {}

    dates = extract_dates(period_text)
    parsed: dict[str, str] = {}
    if len(dates) >= 1:
        parsed["policy_start_date"] = dates[0]
    if len(dates) >= 2:
        parsed["policy_end_date"] = dates[1]
    return parsed


def extract_insurer_name(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str:
    """Extract insurer name from debit note labels and Azure vendor fields."""
    if existing_fields:
        for key in (
            "insurer_name",
            "vendor_name",
            "VendorName",
            "insurer",
            "Insurer",
        ):
            value = existing_fields.get(key)
            if value:
                return _normalize_text(str(value))

    labeled = extract_labeled_value(_lines(text), INSURER_LABELS)
    if labeled:
        return labeled

    for line in _lines(text):
        match = re.search(
            r"(?i)\b(?:insurer(?:\s*name)?|insurance\s*company)\b\s*[:\-]?\s*(.+)$",
            line,
        )
        if match:
            return _normalize_text(match.group(1))
    return ""


def extract_policy_type(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
    layout: dict[str, Any] | None = None,
) -> str:
    """Extract policy type from a ``POLICY TYPE`` label on invoice documents."""
    layout_value = _extract_value_beside_label_from_layout(
        layout,
        label_word_parts=("policy", "type"),
        inline_pattern=re.compile(r"(?i)\bpolicy\s*type\s*[:\-]?\s*(.+)$"),
    )
    if layout_value:
        return layout_value

    text_value = _extract_label_value_from_text(
        text,
        aliases=POLICY_TYPE_LABELS,
        inline_pattern=re.compile(r"(?i)\bpolicy\s*type\s*[:\-]?\s*(.+)$"),
    )
    if text_value:
        return text_value

    if existing_fields:
        for key in ("policy_type", "PolicyType", "policy type"):
            value = existing_fields.get(key)
            if value:
                return _normalize_text(str(value))
    return ""


def extract_purchase_order(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str:
    """Extract a purchase order reference from OCR content."""
    if existing_fields:
        value = existing_fields.get("PurchaseOrder") or existing_fields.get(
            "purchase_order"
        )
        if value:
            return _normalize_text(str(value))

    match = _PURCHASE_ORDER_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return ""


def parse_invoice_document(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
    layout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return CRM-ready keys enriched from invoice OCR text."""
    if not text.strip():
        return {}

    parsed: dict[str, Any] = {}
    invoice_no = extract_invoice_number(text, existing_fields=existing_fields)
    if invoice_no:
        parsed["invoice_no"] = invoice_no
        parsed["InvoiceId"] = invoice_no

    purchase_order = extract_purchase_order(text, existing_fields=existing_fields)
    if purchase_order:
        parsed["purchase_order"] = purchase_order
        parsed["PurchaseOrder"] = purchase_order

    branch = extract_branch(text, existing_fields=existing_fields, layout=layout)
    if branch:
        parsed["branch"] = branch

    insurer_name = extract_insurer_name(text, existing_fields=existing_fields)
    if insurer_name:
        parsed["insurer_name"] = insurer_name
        parsed["vendor_name"] = insurer_name

    parsed.update(extract_policy_period(text, existing_fields=existing_fields))

    policy_type = extract_policy_type(
        text,
        existing_fields=existing_fields,
        layout=layout,
    )
    if policy_type:
        parsed["policy_type"] = policy_type

    total_premium = extract_total_premium(
        text,
        existing_fields=existing_fields,
        layout=layout,
    )
    if total_premium:
        parsed["total_amount"] = total_premium
        parsed["premium_amount"] = total_premium

    return parsed
