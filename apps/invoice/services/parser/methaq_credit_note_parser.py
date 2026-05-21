import re
from datetime import datetime
from .utils import clean_lines, clean_amount


def normalize_methaq_date(value):
    if not value:
        return None

    value = value.strip()

    for fmt in ("%d-%m-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def get_next_value(lines, label, lookahead=5):
    label_lower = label.lower()

    for i, line in enumerate(lines):
        if label_lower in line.lower():

            if ":" in line:
                value = line.split(":", 1)[1].strip()
                if value:
                    return value

            for nxt in lines[i + 1:i + 1 + lookahead]:
                cleaned = nxt.replace(":", "").strip()
                if cleaned:
                    return cleaned

    return None


def parse_methaq_credit_note(raw_text):
    data = {}

    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
    upper_text = compact_text.upper()

    # Basic fields
    data["document_type"] = (
        "TAX CREDIT NOTE"
        if "TAX INVOICE RAISED BY BUYER" in upper_text
        else None
    )

    data["company_name"] = (
        "METHAQ TAKAFUL INSURANCE COMPANY"
        if "METHAQ" in upper_text
        else None
    )

    data["is_methaq"] = "METHAQ" in upper_text

    # Company TRN
    m = re.search(r"TRN\s*:?\s*(\d{15})", compact_text, re.IGNORECASE)
    if m:
        data["tax_registration_number"] = m.group(1)

    # Invoice number / Doc Number
    doc_no = get_next_value(lines, "Doc Number")
    if doc_no:
        m = re.search(r"\bCN/[A-Z]+/\d+\b", doc_no, re.IGNORECASE)
        if m:
            data["invoice_number"] = m.group()

    if not data.get("invoice_number"):
        m = re.search(r"\bCN/[A-Z]+/\d+\b", compact_text, re.IGNORECASE)
        if m:
            data["invoice_number"] = m.group()

    # Issue / invoice date
    m = re.search(r"Issue Date\s*:\s*(\d{2}-\d{2}-\d{4})", compact_text, re.IGNORECASE)
    if m:
        data["invoice_date"] = normalize_methaq_date(m.group(1))

    if not data.get("invoice_date"):
        issue_date = get_next_value(lines, "Issue Date")
        if issue_date:
            m = re.search(r"\d{2}-\d{2}-\d{4}", issue_date)
            if m:
                data["invoice_date"] = normalize_methaq_date(m.group())

    # Branch
    m = re.search(r"Branch\s*:\s*([A-Za-z ]+?)(?:\s+Producer|$)", compact_text, re.IGNORECASE)
    if m:
        data["branch"] = m.group(1).strip()

    # Broker / Producer
    producer = get_next_value(lines, "Producer")
    if producer:
        broker = (
            producer.replace("L.L.C.", "")
            .replace("LLC", "")
            .strip()
        )
        data["broker_name"] = broker

    if not data.get("broker_name"):
        m = re.search(r"Producer\s*:\s*(.+?)\s+Intermediary", compact_text, re.IGNORECASE)
        if m:
            data["broker_name"] = m.group(1).strip()

    data["is_promise_broker"] = (
        "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
    )

    data["broker_validation"] = (
        "VALID" if data["is_promise_broker"] else "NON_PROMISE_BROKER"
    )

    # Broker TRN: second TRN in document
    trns = re.findall(r"TRN\s*:?\s*(\d{15})", compact_text, re.IGNORECASE)
    if len(trns) >= 2:
        data["broker_tax_registration_number"] = trns[1]

    # Participant / insured
    participant = get_next_value(lines, "Participant Name")
    if participant:
        data["insured_name"] = participant

    if not data.get("insured_name"):
        m = re.search(r"Participant Name\s*:\s*(.+?)\s+Insurance Policy No", compact_text, re.IGNORECASE)
        if m:
            data["insured_name"] = m.group(1).strip()

    # Policy number
    policy_no = get_next_value(lines, "Insurance Policy No")
    if policy_no:
        m = re.search(r"\d+", policy_no)
        if m:
            data["policy_number"] = m.group()

    if not data.get("policy_number"):
        m = re.search(r"Insurance Policy No\s*:\s*(\d+)", compact_text, re.IGNORECASE)
        if m:
            data["policy_number"] = m.group(1)

    # Reference number
    ref = get_next_value(lines, "Methaq reference Number")
    if ref:
        data["reference_number"] = ref

    if not data.get("reference_number"):
        m = re.search(r"Methaq reference Number\s*:\s*(\S+)", compact_text, re.IGNORECASE)
        if m:
            data["reference_number"] = m.group(1)

    # Policy period
    m = re.search(
        r"Period of Insurance\s*:\s*From\s*:\s*(\d{2}-[A-Za-z]{3}-\d{4}).*?To\s*:\s*(\d{2}-[A-Za-z]{3}-\d{4})",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["policy_start_date"] = normalize_methaq_date(m.group(1))
        data["policy_end_date"] = normalize_methaq_date(m.group(2))

    # Policy type
    policy_type = get_next_value(lines, "Policy Type")
    if policy_type:
        data["policy_type"] = policy_type

    if not data.get("policy_type"):
        m = re.search(r"Policy Type\s*:\s*(.+?)\s+[\d,]+\.\d{2}", compact_text, re.IGNORECASE)
        if m:
            data["policy_type"] = m.group(1).strip()

    # ---------------------------------------------------
    # COMMISSION / VAT / TOTAL
    # ---------------------------------------------------

    # Commission amount
    for i, line in enumerate(lines):
        if "BEING AGENCY COMMISSION" in line.upper():
            for nxt in lines[i + 1:i + 5]:
                m = re.search(r"[\d,]+\.\d{2}", nxt)

                if m:
                    data["commission_amount"] = clean_amount(m.group())
                    break

            break

    # VAT amount
    for i, line in enumerate(lines):

        if "VAT" in line.upper():

            for nxt in lines[i:i + 4]:
                m = re.search(r"[\d,]+\.\d{2}", nxt)

                if m:
                    data["vat_amount"] = clean_amount(m.group())
                    break

            break

    # Total amount / Net due
    for i, line in enumerate(lines):

        if "NET DUE TO YOU" in line.upper():

            for nxt in lines[i:i + 4]:
                m = re.search(r"[\d,]+\.\d{2}", nxt)

                if m:
                    data["total_amount"] = clean_amount(m.group())
                    break

            break

    # Regex fallback
    if not data.get("commission_amount") or not data.get("vat_amount") or not data.get("total_amount"):
        m = re.search(
            r"Being agency Commission\s+([\d,]+\.\d{2})\s+VAT\s*5%\s+([\d,]+\.\d{2}).*?Net due to you\s+([\d,]+\.\d{2})",
            compact_text,
            re.IGNORECASE,
            )
        if m:
            data["commission_amount"] = clean_amount(m.group(1))
            data["vat_amount"] = clean_amount(m.group(2))
            data["total_amount"] = clean_amount(m.group(3))



    return data