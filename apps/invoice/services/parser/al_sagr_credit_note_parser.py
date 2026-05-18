import re
from datetime import datetime

POLICY_RE = r"P/[A-Z]{2}/\d{4}/\d{2}/\d+"


def clean_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_date(value):
    if not value:
        return None

    value = re.sub(r"[.\-]", "/", value.strip())

    try:
        return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return value


def clean_amount(value):
    if not value:
        return None

    value = value.replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d{2})?", value)

    return match.group() if match else None


def remove_arabic(text):
    if not text:
        return text

    text = re.sub(r"[\u0600-\u06FF]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def is_noise_value(value):
    value = remove_arabic(value).strip()

    noise = [
        "",
        ":",
        ".",
        "..",
        "Date Invoice",
        "Rate Exchange",
        "Code Account",
        "Code Broker",
    ]

    return value in noise


def get_value_after_label(lines, label, lookahead=6):
    label_lower = label.lower()

    for i, line in enumerate(lines):
        if label_lower in line.lower():

            if ":" in line:
                value = line.split(":", 1)[1].strip()
                value = remove_arabic(value)

                if value and not is_noise_value(value):
                    return value

            for nxt in lines[i + 1:i + 1 + lookahead]:
                cleaned = remove_arabic(nxt.replace(":", "").strip())

                if cleaned and not is_noise_value(cleaned):
                    return cleaned

    return None


def is_amount(line):
    return bool(re.fullmatch(r"[\d,]+\.\d{2}", line.strip()))


def parse_al_sagr_credit_note(raw_text):
    data = {}

    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
    clean_text = remove_arabic(compact_text)
    upper_text = clean_text.upper()

    # Basic fields
    data["document_type"] = (
        "CREDIT NOTE"
        if (
            "CREDIT NOTE" in upper_text
            or "TAX INVOICE RAISED BY BUYER" in upper_text
            or "CREDITED YOUR ACCOUNT" in upper_text
            or "WE HAVE CREDITED" in upper_text
            )
            else None
        )
    
    # data["document_type"] = (
    #     "TAX CREDIT NOTE"
    #     if "TAX INVOICE RAISED BY BUYER" in upper_text
    #     else None
    # )

    data["company_name"] = (
        "AL SAGR NATIONAL INSURANCE CO.(PSC)"
        if "AL SAGR" in upper_text or "ASNIC" in upper_text
        else None
    )

    data["is_al_sagr"] = "AL SAGR" in upper_text or "ASNIC" in upper_text

    # Tax registration numbers
    trns = re.findall(r"\b\d{15}\b", clean_text)
    if trns:
        data["tax_registration_number"] = trns[0]

    if len(trns) > 1:
        data["customer_tax_registration_number"] = trns[1]

    # Invoice number
    m = re.search(r"Invoice Number\s+([A-Z0-9\-]+)", clean_text, re.IGNORECASE)
    if m:
        data["invoice_number"] = m.group(1)

    if not data.get("invoice_number"):
        m = re.search(r"\b\d{3}-\d{8}\b", clean_text)
        if m:
            data["invoice_number"] = m.group()

    # Invoice date
    m = re.search(
        r"(\d{2}[./-]\d{2}[./-]\d{4})\s+Date Invoice",
        clean_text,
        re.IGNORECASE,
    )
    if m:
        data["invoice_date"] = normalize_date(m.group(1))

    if not data.get("invoice_date"):
        m = re.search(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", clean_text)
        if m:
            data["invoice_date"] = normalize_date(m.group())

    # Policy number
    m = re.search(POLICY_RE, clean_text)
    if m:
        data["policy_number"] = m.group()

    # Period

    m = re.search(
        r"(?:Period of Ins\.?|Extended Period)\s+"
        r"(\d{2}[./-]\d{2}[./-]\d{4})\s+"
        r"(?:to|To|TO)\s+"
        r"(\d{2}[./-]\d{2}[./-]\d{4})",
        clean_text,
        re.IGNORECASE,
        )

    # m = re.search(
    #     r"Period of Ins\.?\s+(\d{2}[./-]\d{2}[./-]\d{4})\s+to\s+(\d{2}[./-]\d{2}[./-]\d{4})",
    #     clean_text,
    #     re.IGNORECASE,
    # )
    if m:
        data["period_from"] = normalize_date(m.group(1))
        data["period_to"] = normalize_date(m.group(2))

    #line by line fallback 
    if not data.get("period_from"):
        for i, line in enumerate(lines):
            if (
                "PERIOD OF INS" in line.upper()
                or "EXTENDED PERIOD" in line.upper()
            ):

                nearby_text = " ".join(lines[i:i + 4])

                dates = re.findall(
                    r"\d{2}[./-]\d{2}[./-]\d{4}",
                    nearby_text
                )

                if len(dates) >= 2:
                    data["period_from"] = normalize_date(dates[0])
                    data["period_to"] = normalize_date(dates[1])
                break

    # Insured name
    m = re.search(
        r"Insured Name\s+(.+?)\s+Policy Type",
        clean_text,
        re.IGNORECASE,
    )
    if m:
        data["insured_name"] = remove_arabic(m.group(1).strip())

    # Class of insurance
    m = re.search(
        r"Policy Type\s+(.+?)\s+Branch",
        clean_text,
        re.IGNORECASE,
    )
    if m:
        data["policy_type"] = remove_arabic(m.group(1).strip())

    # Branch
    m = re.search(r"Branch\s+(.+?)\s+Department", clean_text, re.IGNORECASE)
    if m:
        data["branch"] = remove_arabic(m.group(1).strip())

    # Account number / Account Code
    for i, line in enumerate(lines):
        if "account code" in line.lower():
            for nxt in lines[i + 1:i + 5]:
                m = re.search(r"\b\d{8}\b", nxt)
                if m:
                    data["account_number"] = m.group()
                    break
            break
        
    # Account name
    m = re.search(
        r"Account\s+Name\s+(.+?)\s+Code Broker",
        clean_text,
        re.IGNORECASE,
    )
    if m:
        data["broker_name"] = remove_arabic(m.group(1).strip())

    # Commission extraction
    commission_items = []

    m = re.search(
        r"Being\s+(\d+(?:\.\d+)?)\s*%\s+(.+?)\s+Commission.*?(\d[\d,]*\.\d{2})\s+(\d[\d,]*\.\d{2})",
        clean_text,
        re.IGNORECASE,
    )

    if m:
        commission_percentage = m.group(1)
        commission_type_raw = m.group(2).strip().upper()
        commission_amount = clean_amount(m.group(3))

        commission_type = commission_type_raw.lower().replace(" ", "_")

        data["commission_percentage"] = commission_percentage
        data["commission_amount"] = commission_amount

        if "OWN DAMAGE" in commission_type_raw:
            data["own_damage_commission_percentage"] = commission_percentage
            data["own_damage_commission_amount"] = commission_amount
            commission_type = "own_damage"

        elif "THIRD PARTY" in commission_type_raw:
            data["third_party_commission_percentage"] = commission_percentage
            data["third_party_commission_amount"] = commission_amount
            commission_type = "third_party"

        commission_items.append({
            "commission_type": commission_type,
            "commission_percentage": commission_percentage,
            "commission_amount": commission_amount,
        })

    data["commission_items"] = commission_items

    # VAT amount
    m = re.search(r"VAT@5%\s+([\d,]+\.\d{2})", clean_text, re.IGNORECASE)
    if m:
        data["vat_amount"] = clean_amount(m.group(1))

    # Total amount
    m = re.search(r"Invoice Total\s+([\d,]+\.\d{2})", clean_text, re.IGNORECASE)
    if m:
        data["total_amount"] = clean_amount(m.group(1))


    return data