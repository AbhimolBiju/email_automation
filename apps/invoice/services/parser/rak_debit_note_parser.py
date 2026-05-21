import re
from datetime import datetime


def clean_amount(value):
    if not value:
        return None

    try:
        return float(str(value).replace(",", "").strip())
    except:
        return None


def clean_text(value):
    if not value:
        return None

    value = re.sub(r"[\u0600-\u06FF]+", "", value)
    value = re.sub(r"\s+", " ", value).strip(" :-")

    return value if len(value) > 1 else None


def normalize_date(value):
    if not value:
        return None

    value = str(value).strip()

    for fmt in ("%d-%B-%Y", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value

def remove_duplicate_phrase(value):
    if not value:
        return value

    value = re.sub(r"[\u0600-\u06FF]+", " ", value)
    value = value.replace(":", " ")
    value = re.sub(r"\s+", " ", value).strip()

    words = value.split()

    # exact half duplicate
    half = len(words) // 2
    if len(words) % 2 == 0 and words[:half] == words[half:]:
        return " ".join(words[:half])

    # partial duplicate cleanup
    best = value

    for split in range(2, len(words)):
        first = words[:split]
        second = words[split:]

        if len(second) >= 2 and first[:len(second)] == second:
            best = " ".join(first)
            break

    return best


def parse_rak_debit_note(text, tables=None):
    data = {}

    lines = []
    seen = set()

    for line in text.splitlines():
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            lines.append(line)

    deduped_text = "\n".join(lines)
    compact_text = re.sub(r"\s+", " ", deduped_text)

    data["insurer_name"] = "RAK Insurance"
    data["premium_currency"] = "AED"

    # Invoice number
    m = re.search(
        r"(DN-\d{2}-\d{2}-\d{2}-[A-Z]{3}-\d+)",
        deduped_text,
        re.IGNORECASE,
    )
    if m:
        data["invoice_number"] = m.group(1).strip()

    # Invoice date
    m = re.search(
        r"Invoice\s*Date\s*:?\s*(\d{1,2}[-/][A-Za-z]+[-/]\d{4})",
        deduped_text,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"Date\s*:?\s*(\d{1,2}[-/][A-Za-z]+[-/]\d{4})",
            deduped_text,
            re.IGNORECASE,
        )
    if m:
        data["invoice_date"] = normalize_date(m.group(1))

    # Insured / account name
    m = re.search(
        r"Account\s*Name\s*:?\s*(.+?)(?:Customer\s*TRN|Customer\s*Address|Account\s*Executive)",
        deduped_text,
        re.IGNORECASE | re.DOTALL,
    )

    if m:
        value = m.group(1)

        value = re.sub(r"[\u0600-\u06FF]+", " ", value)
        value = value.replace(":", " ")
        value = re.sub(r"\s+", " ", value).strip(" :-")
        value = remove_duplicate_phrase(value)

        data["insured_name"] = value

    # Broker name
    m = re.search(
        r"PROMISE\s+INSURANCE\s+SERVICES(?:\s+LLC)?",
        deduped_text,
        re.IGNORECASE,
    )
    if m:
        data["broker_name"] = m.group(0).strip()

    if data.get("broker_name"):
        data["broker_name"] = re.sub(
            r"\s+",
            " ",
            data["broker_name"]
            ).strip()

    if not data.get("broker_name"):
        m = re.search(
            r"Account\s*Executive\s*:?\s*([^\n\r]+)",
            deduped_text,
            re.IGNORECASE,
        )
        if m:
            data["broker_name"] = clean_text(m.group(1))

    # Branch
    m = re.search(
        r"Branch\s*:?\s*([^\n\r]+)",
        deduped_text,
        re.IGNORECASE,
    )
    if m:
        value = m.group(1).split("Policy")[0].strip()
        data["branch"] = clean_text(value)

    # Policy number
    m = re.search(
        r"(P\/\d+\/[A-Z]+\/[A-Z]+\/\d+\/\d+)",
        deduped_text,
        re.IGNORECASE,
    )
    if m:
        data["policy_number"] = m.group(1).strip()

    # Policy type
    m = re.search(
        r"Policy\s*Type\s*:?\s*([^\n\r]+)",
        deduped_text,
        re.IGNORECASE,
    )
    if m:
        value = clean_text(m.group(1))
        value = re.split(
            r"(Quantity|Unit\s*Price|Currency|Premium|VAT|Gross)",
            value,
            flags=re.IGNORECASE,
        )[0].strip()
        data["policy_type"] = value

    # Policy period

    # Start date
    m = re.search(
        r"Policy\s*Inception\s*Date\s*:?\s*(?:\n\s*:?\s*)?(\d{1,2}[-/][A-Za-z]+[-/]\d{4})",
        deduped_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_start_date"] = normalize_date(m.group(1))

    # End date
    m = re.search(
        r"Policy\s*Expiry\s*Date\s*:?\s*(?:\n\s*:?\s*)?(\d{1,2}[-/][A-Za-z]+[-/]\d{4})",
        deduped_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_end_date"] = normalize_date(m.group(1))

    # Net premium
    m = re.search(
        r"(?:Premium\s*Due|Due\s*Premium)\s*:?\s*([\d,]+\.\d{2})",
        deduped_text,
        re.IGNORECASE,
    )
    if m:
        data["net_premium"] = clean_amount(m.group(1))

    # VAT
    m = re.search(
        r"(?:Payable\s*VAT|VAT\s*Payable|VAT).*?([\d,]+\.\d{2})",
        deduped_text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        data["vat_amount"] = clean_amount(m.group(1))

    # Total
    m = re.search(
        r"(?:Gross\s*Amount|Total\s*Amount|Amount\s*Due)\s*:?\s*([\d,]+\.\d{2})",
        deduped_text,
        re.IGNORECASE,
    )
    if m:
        total = clean_amount(m.group(1))
        data["total_amount"] = total
        data["total"] = total
        data["total_premium"] = total
        data["net_due"] = total

    # Fallback total
    if not data.get("total_amount") and data.get("net_premium") and data.get("vat_amount"):
        total = round(data["net_premium"] + data["vat_amount"], 2)
        data["total_amount"] = total
        data["total"] = total
        data["total_premium"] = total
        data["net_due"] = total

    return data