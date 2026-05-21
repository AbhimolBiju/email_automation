import re
from datetime import datetime


def normalize_date(value):
    if not value:
        return None

    value = str(value).strip()
    value = re.sub(r"\s+\d{1,2}:\d{2}", "", value)

    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def clean_amount(value):
    if not value:
        return None

    try:
        return round(float(str(value).replace(",", "").strip()), 2)
    except:
        return None


def parse_methaq_debit_note(text, tables=None):
    data = {}

    data["insurer_name"] = "Methaq"
    data["premium_currency"] = "AED"

    # Invoice number
    m = re.search(
        r"Doc\s*Number\s*:?\s*([A-Z0-9/\-]+)",
        text,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"Debit\s*Note\s*([A-Z0-9/\-]+)",
            text,
            re.IGNORECASE,
        )
    if m:
        data["invoice_number"] = m.group(1).strip()

    # Invoice date
    m = re.search(
        r"Doc\s*Date\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
        text,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"Issue\s*Date\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
            text,
            re.IGNORECASE,
        )
    if m:
        data["invoice_date"] = normalize_date(m.group(1))

    # Branch
    m = re.search(
        r"Branch\s*:?\s*([A-Za-z ]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        data["branch"] = re.sub(r"\s+", " ", m.group(1)).strip()

    # Broker name
    patterns = [
        r"Intermediary\s*Name\s*:?\s*([^\n\r]+)",
        r"Producer\s*:?\s*([^\n\r]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip()
            if len(value) > 2:
                data["broker_name"] = value
                break

    # Insured / participant name
    m = re.search(
        r"Participant\s*Name\s*:?\s*([^\n\r]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        value = m.group(1).strip()
        value = re.split(
            r"(Insurance\s*Policy|Methaq\s*reference|Period\s*of\s*Insurance|Policy\s*Type)",
            value,
            flags=re.IGNORECASE,
        )[0]
        data["insured_name"] = re.sub(r"\s+", " ", value).strip(" :-")

    # Policy number
    m = re.search(
        r"Insurance\s*Policy\s*No\s*:?\s*([A-Z0-9/\-]+)",
        text,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"Policy\s*No\s*:?\s*([A-Z0-9/\-]+)",
            text,
            re.IGNORECASE,
        )
    if m:
        data["policy_number"] = m.group(1).strip()

    # Policy period
    m = re.search(
        r"From\s*:?\s*(\d{1,2}[-/]\w+[-/]\d{4}).{0,80}?To\s*:?\s*(\d{1,2}[-/]\w+[-/]\d{4})",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        data["policy_start_date"] = normalize_date(m.group(1))
        data["policy_end_date"] = normalize_date(m.group(2))

    # Policy type
    m = re.search(
        r"Policy\s*Type\s*:?\s*([^\n\r]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        value = m.group(1)
        value = re.split(
            r"\b(Net\s*due|Amount|Premium|Authorised|AED)\b",
            value,
            flags=re.IGNORECASE,
        )[0]
        data["policy_type"] = re.sub(r"\s+", " ", value).strip(" :-")

    # Total / net due
    m = re.search(
        r"Net\s*due\s*to\s*you\s*:?\s*([\d,]+\.\d{2,3})",
        text,
        re.IGNORECASE,
    )
    if m:
        total = clean_amount(m.group(1))
        data["total_amount"] = total
        data["total"] = total
        data["total_premium"] = total
        data["net_due"] = total

    # Premium + VAT
    m = re.search(
        r"Being\s*Policy\s*Contribution\s*VAT\s*5%\s*([\d,]+\.\d{2,3})\s+([\d,]+\.\d{2,3})",
        text,
        re.IGNORECASE,
    )
    if m:
        data["net_premium"] = clean_amount(m.group(1))
        data["vat_amount"] = clean_amount(m.group(2))

    # Fallback premium + VAT
    if not data.get("net_premium") or not data.get("vat_amount"):
        numbers = re.findall(r"([\d,]+\.\d{2,3})", text)
        cleaned = [clean_amount(n) for n in numbers if clean_amount(n) is not None]

        if len(cleaned) >= 2:
            data["net_premium"] = data.get("net_premium") or cleaned[0]
            data["vat_amount"] = data.get("vat_amount") or cleaned[1]

    # Fallback total
    if not data.get("total_amount") and data.get("net_premium") and data.get("vat_amount"):
        total = round(data["net_premium"] + data["vat_amount"], 2)
        data["total_amount"] = total
        data["total"] = total
        data["total_premium"] = total
        data["net_due"] = total

    return data