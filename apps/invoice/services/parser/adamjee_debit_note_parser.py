import re
from datetime import datetime


def normalize_date(value):
    if not value:
        return None

    value = value.strip()
    value = re.sub(r"\s+\d{1,2}:\d{2}", "", value)
    value = value.replace("/", "-")

    for fmt in ("%d-%m-%Y", "%d-%m-%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def clean_amount(value):
    if not value:
        return None

    try:
        return float(str(value).replace(",", "").strip())
    except:
        return None


def get_value(text, pattern):
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else None


def extract_policy_period(text):
    m = re.search(
        r"PERIOD\s*OF\s*INSURANCE\s*:?\s*FROM\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4}\s+\d{2}:\d{2})"
        r".*?"
        r"TO\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4}\s+\d{2}:\d{2})",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if m:
        return normalize_date(m.group(1)), normalize_date(m.group(2))

    m = re.search(
        r"FROM\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}).*?TO\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if m:
        return normalize_date(m.group(1)), normalize_date(m.group(2))

    return None, None

def extract_broker_name(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]

    for i, line in enumerate(lines):
        if line.lower() in ["to", "to,"]:
            for j in range(i + 1, min(i + 10, len(lines))):
                candidate = lines[j].strip()

                # skip useless lines
                if candidate.lower() in ["account no", "..", ".", ":", "p.o.box,", "p.o.box"]:
                    continue

                if re.match(r"^[A-Z]{2}\d+", candidate):
                    continue

                if any(x in candidate.lower() for x in ["document no", "date", "branch", "department"]):
                    break

                if any(x in candidate.lower() for x in ["insurance", "broker", "services"]):
                    candidate = re.sub(
                        r"P\.?O\.?\s*BOX.*",
                        "",
                        candidate,
                        flags=re.IGNORECASE
                    ).strip(" ,:-")

                    if len(candidate) > 3:
                        return candidate

    # fallback
    m = re.search(
        r"(?:Broker|Brokerage|Intermediary)\s*(?:Name)?\s*:?\s*([^\n\r]+)",
        text,
        re.IGNORECASE,
    )

    if m:
        value = m.group(1).strip(" :,-")
        if len(value) > 2:
            return value

    return None


# def extract_broker_name(text):
#     m = re.search(
#         r"(?:Broker|Brokerage|Intermediary)\s*(?:Name)?\s*:?\s*([^\n\r]+)",
#         text,
#         re.IGNORECASE,
#     )

#     if m:
#         value = m.group(1).strip(" :,-")
#         if len(value) > 2:
#             return value

#     lines = [x.strip() for x in text.splitlines() if x.strip()]

#     for i, line in enumerate(lines):
#         if line.lower() in ["to", "to,"]:
#             for j in range(i + 1, min(i + 5, len(lines))):
#                 candidate = lines[j].strip()

#                 if any(x in candidate.lower() for x in ["account no", "document no", "date"]):
#                     break

#                 if any(x in candidate.lower() for x in ["insurance", "broker", "services"]):
#                     candidate = re.sub(r"P\.?O\.?\s*BOX.*", "", candidate, flags=re.IGNORECASE)
#                     candidate = candidate.strip(" ,:-")
#                     if len(candidate) > 3:
#                         return candidate

#     return None


def extract_invoice_number(text):
    patterns = [
        r"DOCUMENT\s*NO\s*[:\-]?\s*([0-9]{5,})",
        r"TAX\s*INVOICE\s*NO\.?\s*[:\-]?\s*([0-9]{5,})",
        r"INVOICE\s*(?:NO|NUMBER)\.?\s*[:\-]?\s*([0-9]{5,})",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    return None


def extract_invoice_date(text):
    compact = re.sub(r"\s+", " ", text)

    patterns = [
        r"DATE\s*OF\s*ISSUE\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"DOCUMENT\s*DATE\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"INVOICE\s*DATE\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"\bDATE\b\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    ]

    for pattern in patterns:
        m = re.search(pattern, compact, re.IGNORECASE)
        if m:
            return normalize_date(m.group(1))

    return None


def extract_amounts(text):
    result = {
        "net_premium": None,
        "vat_amount": None,
        "total_amount": None,
    }

    net_patterns = [
        r"Premium\s*Excluding\s*VAT\s*Amount\s*:?\s*([\d,]+\.\d{2})",
        r"NET\s*PREMIUM\s*:?\s*([\d,]+\.\d{2})",
        r"([\d,]+\.\d{2})\s*(?:\n|\r|\s)*VAT@\s*5%",
    ]

    for pattern in net_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result["net_premium"] = clean_amount(m.group(1))
            break

    vat_patterns = [
        r"VAT@\s*5%\s*:?\s*([\d,]+\.\d{2})",
        r"VAT\s*Amount\s*:?\s*([\d,]+\.\d{2})",
    ]

    for pattern in vat_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result["vat_amount"] = clean_amount(m.group(1))
            break

    total_patterns = [
        r"Premium\s*Including\s*VAT\s*Amount\s*:?\s*([\d,]+\.\d{2})",
        r"TOTAL\s*PREMIUM\s*:?\s*AED\s*([\d,]+\.\d{2})",
        r"Total\s*:?\s*([\d,]+\.\d{2})",
        r"Grand\s*Total\s*:?\s*([\d,]+\.\d{2})",
    ]

    for pattern in total_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result["total_amount"] = clean_amount(m.group(1))
            break

    if result["total_amount"] is None and result["net_premium"] is not None and result["vat_amount"] is not None:
        result["total_amount"] = round(result["net_premium"] + result["vat_amount"], 2)

    if result["net_premium"] is None and result["total_amount"] is not None and result["vat_amount"] is not None:
        result["net_premium"] = round(result["total_amount"] - result["vat_amount"], 2)

    return result


def parse_adamjee_debit_note(text, tables=None):
    data = {}

    data["insurer_name"] = "Adamjee"

    insured_name = get_value(text, r"NAME\s*OF\s*INSURED\s*:?\s*([^\n\r]+)")
    if insured_name:
        insured_name = insured_name.replace(":", "").strip()

    data["insured_name"] = insured_name

    broker_name = extract_broker_name(text)
    data["broker_name"] = broker_name
    data["is_promise_broker"] = "PROMISE INSURANCE" in (broker_name or "").upper()

    data["invoice_date"] = extract_invoice_date(text)

    branch = get_value(text, r"BRANCH\s*:?\s*([^\n\r]+)")
    data["branch"] = branch.replace(":", "").strip() if branch else None

    policy_type = get_value(text, r"POLICY\s*TYPE\s*:?\s*([^\n\r]+)")
    data["policy_type"] = policy_type.replace(":", "").strip() if policy_type else None

    data["policy_number"] = get_value(text, r"POLICY\s*NO\s*:?\s*([A-Z0-9\-\/]+)")

    data["invoice_number"] = extract_invoice_number(text)

    policy_start_date, policy_end_date = extract_policy_period(text)
    data["policy_start_date"] = policy_start_date
    data["policy_end_date"] = policy_end_date

    data["premium_currency"] = "AED"

    data.update(extract_amounts(text))

    return data