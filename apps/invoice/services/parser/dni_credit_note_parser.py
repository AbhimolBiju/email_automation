import re
from datetime import datetime
from .utils import clean_lines, clean_amount


def normalize_dni_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d-%b-%y").strftime("%Y-%m-%d")
    except Exception:
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


def parse_dni_credit_note(raw_text):
    data = {}

    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
    upper_text = compact_text.upper()

    data["document_type"] = (
        "TAX CREDIT NOTE"
        if "TAX INVOICE RAISED BY BUYER" in upper_text
        else None
    )

    data["company_name"] = (
        "DUBAI NATIONAL INSURANCE & REINSURANCE P.S.C."
        if "DUBAI NATIONAL INSURANCE" in upper_text or "DNI" in upper_text
        else None
    )

    data["is_dni"] = (
        "DUBAI NATIONAL INSURANCE" in upper_text
        or "DNI" in upper_text
    )

    # Broker
    for line in lines:
        if "PROMISE INSURANCE SERVICES" in line.upper():
            broker = (
                line.replace("L.L.C.", "")
                .replace("LLC", "")
                .strip()
            )
            broker = re.sub(r"\(.*?\)", "", broker).strip()
            data["broker_name"] = broker
            break

    if not data.get("broker_name"):
        m = re.search(
            r"(PROMISE\s+INSURANCE\s+SERVICES).*?(?:P O Box|TAX No|Dubai)",
            compact_text,
            re.IGNORECASE,
        )
        if m:
            data["broker_name"] = m.group(1).strip()

    data["is_promise_broker"] = (
        "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
    )

    data["broker_validation"] = (
        "VALID" if data["is_promise_broker"] else "NON_PROMISE_BROKER"
    )

    # Broker TRN
    m = re.search(r"TAX No\s*:?\s*(\d{15})", compact_text, re.IGNORECASE)
    if m:
        data["broker_tax_registration_number"] = m.group(1)

    # Company TRN
    m = re.search(r"Our TAX No\s+(\d{15})", compact_text, re.IGNORECASE)
    if m:
        data["tax_registration_number"] = m.group(1)

    # Invoice number
    invoice_number = get_next_value(lines, "Tax Invoice No")
    if invoice_number:
        m = re.search(r"TXIB-\d+", invoice_number, re.IGNORECASE)
        if m:
            data["invoice_number"] = m.group()

    if not data.get("invoice_number"):
        m = re.search(r"\bTXIB-\d+\b", compact_text, re.IGNORECASE)
        if m:
            data["invoice_number"] = m.group()

    # Invoice date
    invoice_date = get_next_value(lines, "Tax Invoice Date")
    if invoice_date:
        m = re.search(r"\d{2}-[A-Z]{3}-\d{2}", invoice_date, re.IGNORECASE)
        if m:
            data["invoice_date"] = normalize_dni_date(m.group())

    if not data.get("invoice_date"):
        m = re.search(r"\b\d{2}-[A-Z]{3}-\d{2}\b", compact_text, re.IGNORECASE)
        if m:
            data["invoice_date"] = normalize_dni_date(m.group())

    # Branch / division
    division = get_next_value(lines, "Division")
    if division:
        data["branch"] = division

    # Department / policy type
    department = get_next_value(lines, "Department")
    if department:
        data["department"] = department
        data["policy_type"] = department

    # Policy number
    m = re.search(r"Policy No\s+([0-9A-Z/]+)", compact_text, re.IGNORECASE)
    if m:
        data["policy_number"] = m.group(1)

    # Policy period
    m = re.search(
        r"Policy Period\s+(\d{2}-[A-Z]{3}-\d{2}).*?to\s+(\d{2}-[A-Z]{3}-\d{2})",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["policy_start_date"] = normalize_dni_date(m.group(1))
        data["policy_end_date"] = normalize_dni_date(m.group(2))

    # Insured / assured
    assured = get_next_value(lines, "Assured Name")
    if assured:
        data["insured_name"] = assured

    if not data.get("insured_name"):
        m = re.search(r"Assured Name\s+(.+?)\s+Class of business", compact_text, re.IGNORECASE)
        if m:
            data["insured_name"] = m.group(1).strip()

    
    # Commission percentage
    m = re.search(r"Being\s+(\d+(?:\.\d+)?)\s*%\s+Commission", compact_text, re.IGNORECASE)
    if m:
        data["commission_percentage"] = m.group(1)

    # Amounts line/table
    amounts = re.findall(r"\b\d+(?:,\d{3})*\.\d{2}\b", compact_text)

    # Expected table sequence includes 380.00, 380.00, 19.00, 399.00
    if len(amounts) >= 4:
        data["commission_amount"] = clean_amount(amounts[-4])
        data["vat_amount"] = clean_amount(amounts[-2])
        data["total_amount"] = clean_amount(amounts[-1])

    # Safer fallback around TOTAL row
    m = re.search(
        r"TOTAL:.*?([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["commission_amount"] = clean_amount(m.group(1))
        data["vat_amount"] = clean_amount(m.group(3))
        data["total_amount"] = clean_amount(m.group(4))

    data["commission_items"] = []

    if data.get("commission_amount"):
        data["commission_items"].append({
            "commission_type": "commission",
            "commission_percentage": data.get("commission_percentage"),
            "commission_amount": data["commission_amount"],
        })

    return data