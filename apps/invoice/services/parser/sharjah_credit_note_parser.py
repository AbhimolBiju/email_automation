import re
from .utils import clean_lines, normalize_date, clean_amount


def get_next_value(lines, label, lookahead=6):
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


def parse_sharjah_credit_note(raw_text):
    data = {}

    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
    upper_text = compact_text.upper()

    data["document_type"] = "CREDIT NOTE" if "CREDIT NOTE" in upper_text else None
    data["company_name"] = "SHARJAH INSURANCE COMPANY PSC" if "SHARJAH INSURANCE" in upper_text else None
    data["is_sharjah"] = "SHARJAH INSURANCE" in upper_text

    # Branch
    branch = get_next_value(lines, "Branch")
    if branch:
        data["branch"] = branch

    # Policy type
    policy_type = get_next_value(lines, "Policy Type")
    if policy_type:
        data["policy_type"] = policy_type

    # Invoice / credit note number
    credit_no = get_next_value(lines, "Credit Note No")
    if credit_no:
        m = re.search(r"\d{4}-\d{2}-\d+", credit_no)
        if m:
            data["invoice_number"] = m.group()

    if not data.get("invoice_number"):
        m = re.search(r"\b\d{4}-\d{2}-\d+\b", compact_text)
        if m:
            data["invoice_number"] = m.group()

    # Invoice date
    date_value = get_next_value(lines, "Date")
    if date_value:
        m = re.search(r"\d{2}[./-]\d{2}[./-]\d{4}", date_value)
        if m:
            data["invoice_date"] = normalize_date(m.group())

    if not data.get("invoice_date"):
        m = re.search(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", compact_text)
        if m:
            data["invoice_date"] = normalize_date(m.group())

    # Account number
    account_code = get_next_value(lines, "Account Code")
    if account_code:
        data["account_number"] = account_code

    # Broker name
    broker = get_next_value(lines, "Account Name")
    if broker:
        broker = (
            broker.replace("L.L.C.", "")
            .replace("LLC", "")
            .replace("- DUBAI BRANCH", "")
            .strip()
        )
        data["broker_name"] = broker

    if not data.get("broker_name"):
        m = re.search(r"(PROMISE\s+INSURANCE\s+SERVICES)", compact_text, re.IGNORECASE)
        if m:
            data["broker_name"] = m.group(1).strip()

    data["is_promise_broker"] = (
        "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
    )
    data["broker_validation"] = "VALID" if data["is_promise_broker"] else "NON_PROMISE_BROKER"

    # Broker TRN
    vat_no = get_next_value(lines, "VAT No")
    if vat_no:
        m = re.search(r"\d{15}", vat_no)
        if m:
            data["broker_tax_registration_number"] = m.group()

    # Insured name
    assured = get_next_value(lines, "Assured Name")
    if assured:
        data["insured_name"] = assured

    # Policy number
    policy_no = get_next_value(lines, "Policy No")
    if policy_no:
        m = re.search(r"P/\d+/\d+/\d+/\d+/\d+", policy_no)
        if m:
            data["policy_number"] = m.group()

    if not data.get("policy_number"):
        m = re.search(r"P/\d+/\d+/\d+/\d+/\d+", compact_text)
        if m:
            data["policy_number"] = m.group()

    # Commission percentage
    m = re.search(r"Being\s+(\d+(?:\.\d+)?)\s*%\s+Commission", compact_text, re.IGNORECASE)
    if m:
        data["commission_percentage"] = m.group(1)

    # Amounts
    amounts = re.findall(r"\b\d+(?:,\d{3})*\.\d{2}\b", compact_text)

    if len(amounts) >= 3:
        data["commission_amount"] = clean_amount(amounts[0])
        data["vat_amount"] = clean_amount(amounts[1])
        data["total_amount"] = clean_amount(amounts[-1])

    # Strong fallback by known table pattern
    m = re.search(
        r"Commission.*?([\d,]+\.\d{2}).*?VAT.*?([\d,]+\.\d{2}).*?TOTAL.*?([\d,]+\.\d{2})",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["commission_amount"] = clean_amount(m.group(1))
        data["vat_amount"] = clean_amount(m.group(2))
        data["total_amount"] = clean_amount(m.group(3))

    data["commission_items"] = []
    if data.get("commission_amount"):
        data["commission_items"].append({
            "commission_type": "commission",
            "commission_percentage": data.get("commission_percentage"),
            "commission_amount": data["commission_amount"],
        })

    # Vehicle details
    
    period = get_next_value(lines, "Period of Ins")
    if period:
        dates = re.findall(r"\d{2}[./-]\d{2}[./-]\d{4}", period)
        if len(dates) >= 2:
            data["policy_start_date"] = normalize_date(dates[0])
            data["policy_end_date"] = normalize_date(dates[1])

    return data