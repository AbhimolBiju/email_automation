import re
from datetime import datetime


def clean_amount(value):
    if not value:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except:
        return None


def clean_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_date(value):
    if not value:
        return None

    value = str(value).strip().upper()

    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def extract_policy_date_range(text):
    if not text:
        return None, None

    date_pattern = r"\d{1,2}[-/][A-Z]{3}[-/]\d{2,4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"

    m = re.search(
        rf"Policy\s*Period\s*({date_pattern})\s*(?:to|-)\s*({date_pattern})",
        text,
        re.IGNORECASE,
    )

    if m:
        return normalize_date(m.group(1)), normalize_date(m.group(2))

    return None, None


def parse_dni_debit_note(text, tables=None):
    data = {}

    lines = clean_lines(text)
    compact_text = re.sub(r"\s+", " ", text)

    data["insurer_name"] = "Dubai National Insurance"
    data["premium_currency"] = "AED"

    # Invoice number
    m = re.search(
        r"Tax\s*Invoice\s*No\s*[:\s]+([A-Z0-9/\-]+)",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["invoice_number"] = m.group(1).strip()

    # Invoice date
    m = re.search(
        r"Tax\s*Invoice\s*Date\s*[:\s]+([0-9]{1,2}-[A-Z]{3}-[0-9]{2,4})",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["invoice_date"] = normalize_date(m.group(1))

    # Insured name / Assured name
    m = re.search(
        r"Assured\s*Name\s+(.+?)\s+Class\s*of\s*business",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["insured_name"] = re.sub(r"\s+", " ", m.group(1)).strip()

    if not data.get("insured_name"):
        m = re.search(
            r"To\s+(.+?)\s+Insured\s*TAX",
            compact_text,
            re.IGNORECASE,
        )
        if m:
            value = m.group(1)
            value = re.sub(r"\(.*?\)", "", value)
            value = re.sub(r"\b\d{5,}\b", "", value)
            value = re.split(
                r"(Ras al|Dubai|Abu Dhabi|United Arab Emirates|UAE)",
                value,
                flags=re.IGNORECASE,
            )[0]
            data["insured_name"] = re.sub(r"\s+", " ", value).strip(" :-")

    # Broker name
    m = re.search(
        r"Account\s*No\s+([A-Z0-9\-\/]+)\s+(.+?)\s+Registration\s*No",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["broker_name"] = re.sub(r"\s+", " ", m.group(2)).strip()

    # Branch
    m = re.search(
        r"Division\s+([A-Z ]+?)\s+Department",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["branch"] = m.group(1).strip().title()

    # Policy type

    # Priority 1: Department
    m = re.search(
        r"Department\s+([A-Za-z ]+?)\s+Our\s*TAX\s*No",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_type"] = re.sub(r"\s+", " ", m.group(1)).strip()

    # Priority 2: Class of business
    if not data.get("policy_type"):
        m = re.search(
            r"Class\s*of\s*business\s+([A-Za-z ]+?)\s+Sub\s*class",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["policy_type"] = re.sub(r"\s+", " ", m.group(1)).strip()

    # Priority 3: Sub class fallback only
    if not data.get("policy_type"):
        m = re.search(
            r"Sub\s*class\s+(.+?)\s+Account\s*No",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["policy_type"] = re.sub(r"\s+", " ", m.group(1)).strip()


    if not data.get("policy_type"):
        m = re.search(
            r"Class\s*of\s*business\s+(.+?)\s+Sub\s*class",
            compact_text,
            re.IGNORECASE,
        )
        if m:
            data["policy_type"] = re.sub(r"\s+", " ", m.group(1)).strip()

    # Policy number
    m = re.search(
        r"Policy\s*No\.?\s+([A-Z0-9\/\-]+)",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["policy_number"] = m.group(1).strip()

    # Policy period
    start_date, end_date = extract_policy_date_range(compact_text)
    data["policy_start_date"] = start_date
    data["policy_end_date"] = end_date

    # Amounts from TOTAL row
    m = re.search(
        r"TOTAL:\s*\(IN\s*AED\)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["net_premium"] = clean_amount(m.group(2))
        data["vat_amount"] = clean_amount(m.group(3))
        total = clean_amount(m.group(4))

        data["total_amount"] = total
        data["total"] = total
        data["total_premium"] = total
        data["net_due"] = total

    # Fallback: use last 3 amounts
    if not data.get("total_amount"):
        numbers = re.findall(r"([\d,]+\.\d{2,3})", compact_text)
        cleaned = [clean_amount(n) for n in numbers if clean_amount(n) is not None]

        if len(cleaned) >= 3:
            data["net_premium"] = cleaned[-3]
            data["vat_amount"] = cleaned[-2]
            total = cleaned[-1]

            data["total_amount"] = total
            data["total"] = total
            data["total_premium"] = total
            data["net_due"] = total

    return data