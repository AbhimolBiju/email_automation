import re
from datetime import datetime

POLICY_RE = r"P-\d{4}-\d{2}-\d{4}-\d+"


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

def get_next_value(lines, label, lookahead=5):
    label_lower = label.lower()

    for i, line in enumerate(lines):
        if label_lower in line.lower():

            # same line value after :
            if ":" in line:
                value = line.split(":", 1)[1].strip()
                if value:
                    return value

            # next line value
            for nxt in lines[i + 1:i + 1 + lookahead]:
                cleaned = nxt.replace(":", "").strip()

                if not cleaned:
                    continue

                if cleaned in [".", "..", ". .", ":"]:
                    continue

                return cleaned

    return None


def is_amount(line):
    return bool(re.fullmatch(r"[\d,]+\.\d{2}", line.strip()))


def parse_adamjee_credit_note(raw_text):

    data = {}

    lines = clean_lines(raw_text)
    lines = [remove_arabic(line) for line in lines]
    lines = [line for line in lines if line]


    compact_text = " ".join(lines)
    clean_text = remove_arabic(compact_text)
    upper_text = compact_text.upper()

    # ---------------------------------------------------
    # BASIC IDENTIFICATION
    # ---------------------------------------------------

    data["document_type"] = (
        "CREDIT NOTE"
        if "CREDIT NOTE" in upper_text
        else None
    )

    data["company_name"] = (
        "ADAMJEE INSURANCE CO. LTD"
        if "ADAMJEE" in upper_text
        else None
    )

    data["is_adamjee"] = (
        True
        if "ADAMJEE" in upper_text
        else False
    )

    # ---------------------------------------------------
    # VAT REGISTRATION NUMBER
    # ---------------------------------------------------

    m = re.search(r"VAT REGISTRATION NO\s*:?\s*(\d{15})", clean_text, re.IGNORECASE)

    if m:
        data["tax_registration_number"] = m.group(1)

    # ---------------------------------------------------
    # INVOICE NUMBER / DOCUMENT NUMBER
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if "DOCUMENT NO" in line.upper():
            for nxt in lines[i:i + 4]:
                m = re.search(r"\b\d{6,}\b", nxt)
                if m:
                    data["invoice_number"] = m.group()
                    break
            break

    # ---------------------------------------------------
    # DATE
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if line.upper().startswith("DATE"):
            for nxt in lines[i:i + 4]:
                m = re.search(r"\d{2}[./-]\d{2}[./-]\d{4}", nxt)
                if m:
                    data["invoice_date"] = normalize_date(m.group())
                    break
            break

    # ---------------------------------------------------
    # BRANCH
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if line.upper().startswith("BRANCH"):
            for nxt in lines[i + 1:i + 5]:
                if nxt.strip() in [":", ".", "..", ". ."]:
                    continue
                if "DEPARTMENT" in nxt.upper():
                    continue

                data["branch"] = nxt.strip()
                break
            break

    # ---------------------------------------------------
    # ACCOUNT NUMBER
    # ---------------------------------------------------

    m = re.search(r"\bAB\d+\b", clean_text, re.IGNORECASE)

    if m:
        data["account_number"] = m.group()

    # ---------------------------------------------------
    # BROKER NAME
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if "PROMISE INSURANCE SERVICES" in line.upper():
            broker_name = line.strip()
            broker_name = broker_name.replace("L.L.C.", "")
            broker_name = broker_name.replace("LLC", "")
            broker_name = broker_name.strip()

            data["broker_name"] = broker_name
            break


    # ---------------------------------------------------
    # INSURED NAME
    # ---------------------------------------------------


    for i, line in enumerate(lines):
        if "NAME OF INSURED" in line.upper():
            insured_parts = []

            if ":" in line:
                value = line.split(":", 1)[1].strip()
            else:
                value = line.replace("NAME OF INSURED", "").strip()

            if value:
                insured_parts.append(value)

            for nxt in lines[i + 1:i + 5]:
                cleaned = nxt.strip()
                upper = cleaned.upper()

                if (
                    "REFERENCE NO" in upper
                    or "ADDRESS" in upper
                    or "POLICY NO" in upper
                    or "END. NO" in upper
                    or "POLICY TYPE" in upper
                    ):
                    break
                if cleaned:
                    insured_parts.append(cleaned)

            if insured_parts:
                data["insured_name"] = " ".join(insured_parts)

            break

    # for line in lines:
    #     if "NAME OF INSURED" in line.upper():
    #         if ":" in line:
    #             insured_name = line.split(":", 1)[1].strip()
    #         else:
    #             insured_name = line.replace("NAME OF INSURED", "").strip()

    #         if insured_name:
    #             data["insured_name"] = insured_name
    #         break


    # ---------------------------------------------------
    # POLICY NUMBER
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if "POLICY NO" in line.upper():
            for nxt in lines[i:i + 4]:
                m = re.search(POLICY_RE, nxt)
                if m:
                    data["policy_number"] = m.group()
                    break
            break

    if not data.get("policy_number"):
        m = re.search(POLICY_RE, clean_text)
        if m:
            data["policy_number"] = m.group()  


    # ---------------------------------------------------
    # POLICY TYPE / INSURANCE TYPE
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if "POLICY TYPE" in line.upper():
            for nxt in lines[i + 1:i + 5]:
                if nxt.strip() in [":", ".", "..", ". ."]:
                    continue
                if "CERTIFICATE" in nxt.upper():
                    continue

                data["policy_type"] = nxt.strip()
                break
            break


    # ---------------------------------------------------
    # PERIOD
    # ---------------------------------------------------

    m = re.search(
        r"PERIOD OF INSURANCE\s*:\s*FROM\s+(\d{2}[./-]\d{2}[./-]\d{4}).+?To\s+(\d{2}[./-]\d{2}[./-]\d{4})",
        clean_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_start_date"] = normalize_date(m.group(1))
        data["policy_end_date"] = normalize_date(m.group(2))


    # ---------------------------------------------------
    # COMMISSION EXTRACTION
    # ---------------------------------------------------

    commission_items = []
    for i, line in enumerate(lines):
        if "COMMISSION" in line.upper():
            percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)

            commission_percentage = (
                percent_match.group(1)
                if percent_match
                else None
            )

            amount = None

            for nxt in lines[i:i + 5]:
                if is_amount(nxt):
                    amount = clean_amount(nxt)
                    break

            item = {
                "commission_type": "commission",
                "commission_percentage": commission_percentage,
                "commission_amount": amount,
            }
            commission_items.append(item)

            data["commission_percentage"] = commission_percentage
            data["commission_amount"] = amount
            break

    data["commission_items"] = commission_items 



    # ---------------------------------------------------
    # VAT AMOUNT
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        line_upper = line.upper()

        if "VAT@" in line_upper or "VAT@ 5%" in line_upper:
            amount = re.search(r"([\d,]+\.\d{2})", line)

            if amount:
                data["vat_amount"] = clean_amount(amount.group(1))

            else:
                for nxt in lines[i + 1:i + 4]:
                    if is_amount(nxt):
                        data["vat_amount"] = clean_amount(nxt)
                        break
            break


    # ---------------------------------------------------
    # TOTAL AMOUNT
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if "NET DUE" in line.upper():
            for nxt in lines[i:i + 4]:
                if is_amount(nxt):
                    data["total_amount"] = clean_amount(nxt)
                    break
            break


    # ---------------------------------------------------
    # REFERENCE NUMBER
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if "REFERENCE NO" in line.upper():
            for nxt in lines[i:i + 3]:
                m = re.search(r"\d+", nxt)
                if m:
                    data["reference_number"] = m.group()
                    break
            break  
    return data