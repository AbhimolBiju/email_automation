import re
from datetime import datetime


def clean_amount(value):
    if not value:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except:
        return None


def normalize_date(value):
    if not value:
        return None

    value = str(value).strip()

    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def clean_text(value):
    if not value:
        return None

    value = re.sub(r"\s+", " ", value).strip(" :-")
    return value if len(value) > 1 else None


def parse_watania_debit_note(text, tables=None):
    data = {}

    raw_text = text or ""
    compact_text = re.sub(r"\s+", " ", raw_text)

    data["doc_type"] = "debit_note"
    data["insurer_name"] = "Watania Takaful"
    data["premium_currency"] = "AED"

    # Invoice number / document number
    patterns = [
        r"Document\s+No\.?\s*:?\s*([A-Z0-9\-]+)",
        r"Original\s+Tax\s+Invoice\s+No\.?\s*:?\s*([A-Z0-9\-]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, raw_text, re.IGNORECASE)
        if m:
            data["invoice_number"] = m.group(1).strip()
            break

    # Invoice date
    m = re.search(
        r"Invoice\s+Date\s*:?\s*(\d{2}/\d{2}/\d{4})",
        raw_text,
        re.IGNORECASE,
    )
    if m:
        data["invoice_date"] = normalize_date(m.group(1))

    # Insured / customer name
    patterns = [
        r"Client\s+Name\s*:?\s*([^\n\r]+)",
        r"Original\s+Assured\s*:?\s*[A-Z0-9\-]+\s+([A-Z\s]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, raw_text, re.IGNORECASE)
        if m:
            value = clean_text(m.group(1))
            if value and value.upper() not in ["AED", "UAE", "NULL", "NIL"]:
                data["insured_name"] = value
                break

    # Broker name
    m = re.search(
        r"Broker\s+Name\s*:?\s*([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )
    if m:
        value = m.group(1).split("(")[0]
        data["broker_name"] = clean_text(value)

    # Policy number / takaful certificate
    patterns = [
        r"in\s+respect\s+of\s+our\s+Takaful\s+Certificate\s+([A-Z0-9]+)",
        r"Takaful\s+Certificate\s+([A-Z0-9]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, raw_text, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            if len(value) >= 6:
                data["policy_number"] = value
                break

    # Policy type
    m = re.search(
        r"Takaful\s+Certificate\s+Type\s*:?\s*([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_type"] = clean_text(m.group(1))
    elif "mumtaz" in raw_text.lower():
        data["policy_type"] = "Mumtaz (2.0)"

    # Policy period
    period_patterns = [
        r"for\s+the\s+period\s+of\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})",
        r"period\s+of\s+insurance.*?(\d{2}/\d{2}/\d{4}).*?(\d{2}/\d{2}/\d{4})",
        r"policy\s+period.*?(\d{2}/\d{2}/\d{4}).*?(\d{2}/\d{2}/\d{4})",
    ]

    for pattern in period_patterns:
        m = re.search(pattern, compact_text, re.IGNORECASE | re.DOTALL)
        if m:
            data["policy_start_date"] = normalize_date(m.group(1))
            data["policy_end_date"] = normalize_date(m.group(2))
            break

    # Net premium / contribution
    amount_patterns = [
        r"Total\s+Contribution\s*:?\s*([\d,]+\.\d+)",
        r"Contribution\s+Amount\s+Due\s*:?\s*([\d,]+\.\d+)",
        r"Contribution\s+Amount\s*:?\s*([\d,]+\.\d+)",
    ]

    for pattern in amount_patterns:
        m = re.search(pattern, compact_text, re.IGNORECASE)
        if m:
            data["net_premium"] = clean_amount(m.group(1))
            break

    # VAT
    m = re.search(
        r"VAT\s*5%.*?([\d,]+\.\d+)",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["vat_amount"] = clean_amount(m.group(1))
    # m = re.search(
    #     r"VAT\s*5%\s*:?\s*([\d,]+\.\d+)",
    #     compact_text,
    #     re.IGNORECASE,
    # )
    # if m:
    #     data["vat_amount"] = clean_amount(m.group(1))

    # Total
    total_patterns = [
        r"Total\s+([\d,]+\.\d+)\s*AED",
        r"Grand\s+Total\s+([\d,]+\.\d+)",
        r"Total\s+Amount\s+Payable\s*([\d,]+\.\d+)",
    ]

    for pattern in total_patterns:
        matches = re.findall(pattern, compact_text, re.IGNORECASE)
        if matches:
            values = [clean_amount(x) for x in matches if clean_amount(x) is not None]
            if values:
                total = max(values)
                data["total_amount"] = total
                data["total"] = total
                data["total_premium"] = total
                data["net_due"] = total
                break

    # Fallback total
    if not data.get("total_amount") and data.get("net_premium") and data.get("vat_amount"):
        total = round(data["net_premium"] + data["vat_amount"], 2)
        data["total_amount"] = total
        data["total"] = total
        data["total_premium"] = total
        data["net_due"] = total

    return data