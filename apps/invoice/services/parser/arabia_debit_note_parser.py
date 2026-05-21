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

    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def extract_policy_date_range(text):
    m = re.search(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        text,
        re.IGNORECASE,
    )
    if m:
        return normalize_date(m.group(1)), normalize_date(m.group(2))

    return None, None


def parse_arabia_debit_note(text, tables=None):
    data = {}

    compact_text = re.sub(r"\s+", " ", text)

    data["insurer_name"] = "Arabia Insurance"
    data["premium_currency"] = "AED"

    # Invoice number
    m = re.search(
        r"(TDN\s*/\s*[A-Z]{2}\s*/\s*\d{4}\s*/\s*\d+)",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["invoice_number"] = re.sub(r"\s+", "", m.group(1))

    # Invoice date
    patterns = [
        r"Tax\s*Invoice\s*Date\s*[:\-]?\s*([0-9]{2}-[A-Z]{3}-[0-9]{2,4})",
        r"Invoice\s*Date\s*([0-9]{2}-[A-Z]{3}-[0-9]{2,4})",
        r"([0-9]{2}-[A-Z]{3}-[0-9]{2,4})",
    ]

    for pattern in patterns:
        m = re.search(pattern, compact_text, re.IGNORECASE)
        if m:
            data["invoice_date"] = normalize_date(m.group(1).upper())
            break

    # Insured / customer name
    m = re.search(
        r"Customer\s*:?\s*([A-Za-z0-9&.\- ]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        value = m.group(1).strip()
        value = re.split(r"\d{3,}|United Arab Emirates|\n", value)[0].strip()
        data["insured_name"] = value

    # Broker name
    broker_patterns = [
        r"(?:Insurance\s*Broker|Broker|Brokerage|Intermediary)\s*(?:Name)?\s*:?\s*([^\n\r]+)",
        r"Through\s*(?:Broker|Intermediary)?\s*:?\s*([^\n\r]+)",
        r"Broker\s*Name\s*:?\s*([^\n\r]+)",
    ]

    for pattern in broker_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            value = re.split(
                r"(policy|invoice|date|department|currency)",
                value,
                flags=re.IGNORECASE,
            )[0].strip()
            if len(value) > 2:
                data["broker_name"] = value
                break

    # Branch
    m = re.search(
        r"Branch\s*([^\n]+?)\s*Department",
        text,
        re.IGNORECASE,
    )
    if m:
        data["branch"] = m.group(1).strip()
    else:
        m = re.search(r"Branch\s*([^\n]+)", text, re.IGNORECASE)
        if m:
            value = m.group(1)
            value = value.split("Paid Up Capital")[0]
            value = value.split("Subject")[0]
            data["branch"] = value.strip()

    # Policy type
    patterns = [
        r"Department\s*:?\s*([A-Za-z ]+)",
        r"Description\s*:?\s*([A-Za-z ]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip()
            if len(value) > 2:
                data["policy_type"] = value
                break

    # Policy number
    patterns = [
        r"Policy\s*No\s*[:\-]?\s*([A-Z0-9\/\-]+)",
        r"Motor\s*Insurance\s*Policy\s*No\s*([A-Z0-9\/\-]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            if len(value) >= 5:
                data["policy_number"] = value
                break

    # Policy period
    start_date, end_date = extract_policy_date_range(compact_text)
    data["policy_start_date"] = start_date
    data["policy_end_date"] = end_date

    # Amounts
    m = re.search(
        r"Policy\s*Premium\s*([\d,]+\.\d+)", 
        compact_text, 
        re.IGNORECASE)
    if not m:
        m = re.search(
            r"Gross\s*Premium\s*([\d,]+\.\d+)", 
            compact_text, 
            re.IGNORECASE)
    if m:
        data["net_premium"] = clean_amount(m.group(1))

    m = re.search(
        r"Taxe?\s*Value\s*([\d,]+\.\d+)", 
        compact_text, 
        re.IGNORECASE)
    if not m:
        m = re.search(
            r"VAT\s*Amount\s*([\d,]+\.\d+)", 
            compact_text, 
            re.IGNORECASE)
    if m:
        data["vat_amount"] = clean_amount(m.group(1))

    m = re.search(
        r"Gross\s*Prem\s*with\s*VAT\s*([\d,]+\.\d+)",
        compact_text,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(r"Total\s*Amount\s*([\d,]+\.\d+)", compact_text, re.IGNORECASE)

    if m:
        total = clean_amount(m.group(1))
        data["total"] = total
        data["total_amount"]=total
        data["total_premium"] = total
        data["net_due"] = total

    if not data.get("total") and data.get("net_premium") and data.get("vat_amount"):
        total = round(data["net_premium"] + data["vat_amount"], 3)
        data["total_amount"]=total 
        data["total"] = total
        data["total_premium"] = total
        data["net_due"] = total

    return data