import re
from datetime import datetime
from .utils import clean_lines, clean_amount


def normalize_arabia_date(value):
    if not value:
        return None

    value = value.strip()

    try:
        return datetime.strptime(value, "%d-%b-%y").strftime("%Y-%m-%d")
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


def parse_arabia_credit_note(raw_text):
    data = {}

    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
    upper_text = compact_text.upper()

    # ---------------------------------------------------
    # BASIC IDENTIFICATION
    # ---------------------------------------------------

    data["document_type"] = (
        "TAX CREDIT NOTE"
        if "TAX INVOICE RAISED BY BUYER" in upper_text
        else None
    )

    data["company_name"] = (
        "ARABIA INSURANCE CO. S.A.L."
        if "ARABIA INSURANCE" in upper_text
        else None
    )

    data["is_arabia"] = "ARABIA INSURANCE" in upper_text

    # ---------------------------------------------------
    # TAX REGISTRATION NUMBER
    # ---------------------------------------------------

    trn = get_next_value(lines, "TRN")

    if trn:
        m = re.search(r"\d{15}", trn)
        if m:
            data["tax_registration_number"] = m.group()

    if not data.get("tax_registration_number"):
        m = re.search(r"TRN\s*:?\s*(\d{15})", compact_text, re.IGNORECASE)
        if m:
            data["tax_registration_number"] = m.group(1)

    # ---------------------------------------------------
    # INVOICE NUMBER
    # ---------------------------------------------------

    invoice_number = get_next_value(lines, "Invoice Number")

    if invoice_number:
        m = re.search(r"\bTCN/[A-Z]+/\d{4}/\d+\b", invoice_number)
        if m:
            data["invoice_number"] = m.group()

    if not data.get("invoice_number"):
        m = re.search(r"\bTCN/[A-Z]+/\d{4}/\d+\b", compact_text)
        if m:
            data["invoice_number"] = m.group()

    # ---------------------------------------------------
    # INVOICE DATE
    # ---------------------------------------------------

    invoice_date = get_next_value(lines, "Tax Invoice Date")

    if invoice_date:
        m = re.search(r"\d{2}-[A-Z]{3}-\d{2}", invoice_date, re.IGNORECASE)
        if m:
            data["invoice_date"] = normalize_arabia_date(m.group())

    if not data.get("invoice_date"):
        m = re.search(r"\b\d{2}-[A-Z]{3}-\d{2}\b", compact_text, re.IGNORECASE)
        if m:
            data["invoice_date"] = normalize_arabia_date(m.group())

    # ---------------------------------------------------
    # BROKER NAME
    # ---------------------------------------------------

    broker = get_next_value(lines, "Bill by")

    if broker:
        broker = (
            broker.replace("L L C", "")
            .replace("L.L.C.", "")
            .replace("LLC", "")
            .strip()
        )

        data["broker_name"] = broker

    if not data.get("broker_name"):
        m = re.search(r"Bill by:\s*(.+?)\s+Address:", compact_text, re.IGNORECASE)

        if m:
            broker = (
                m.group(1)
                .replace("L L C", "")
                .replace("L.L.C.", "")
                .replace("LLC", "")
                .strip()
            )

            data["broker_name"] = broker

    data["is_promise_broker"] = (
        "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
    )

    data["broker_validation"] = (
        "VALID"
        if data["is_promise_broker"]
        else "NON_PROMISE_BROKER"
    )

    # ---------------------------------------------------
    # BROKER TRN
    # ---------------------------------------------------

    broker_trn = get_next_value(lines, "Producer TAX Reg")

    if broker_trn:
        m = re.search(r"\d{15}", broker_trn)
        if m:
            data["broker_tax_registration_number"] = m.group()

    if not data.get("broker_tax_registration_number"):
        m = re.search(r"Producer TAX Reg:\s*(\d{15})", compact_text, re.IGNORECASE)

        if m:
            data["broker_tax_registration_number"] = m.group(1)

    # ---------------------------------------------------
    # BRANCH
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if line.strip().upper() == "BRANCH":
            for nxt in lines[i + 1:i + 4]:
                cleaned = nxt.strip()

                if cleaned:
                    data["branch"] = cleaned
                    break

            break

    # fallback
    if not data.get("branch"):
        m = re.search(
            r"Tax Invoice Date\s+\d{2}-[A-Z]{3}-\d{2}\s+Branch\s+(.+?)\s+Department",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["branch"] = m.group(1).strip()

    # ---------------------------------------------------
    # DEPARTMENT / POLICY TYPE
    # ---------------------------------------------------

    department = get_next_value(lines, "Department")

    if department:
        data["department"] = department

    if "MOTOR INSURANCE" in upper_text:
        data["policy_type"] = "Motor Insurance"

    if not data.get("department") and data.get("policy_type"):
        data["department"] = data["policy_type"]

    # ---------------------------------------------------
    # POLICY NUMBER
    # ---------------------------------------------------

    for line in lines:
        if "POLICY NO" in line.upper():
            m = re.search(r"[A-Z]+/[A-Z]+/\d{4}/\d+", line, re.IGNORECASE)

            if m:
                data["policy_number"] = m.group()
                break

    if not data.get("policy_number"):
        m = re.search(r"Policy No\s+([A-Z]+/[A-Z]+/\d{4}/\d+)", compact_text, re.IGNORECASE)

        if m:
            data["policy_number"] = m.group(1)

    # ---------------------------------------------------
    # CURRENCY
    # ---------------------------------------------------

    currency = get_next_value(lines, "Currency")

    if currency:
        data["currency"] = currency

    if not data.get("currency") and "AED" in upper_text:
        data["currency"] = "AED"

    # ---------------------------------------------------
    # COMMISSION AMOUNT
    # ---------------------------------------------------

    commission = get_next_value(lines, "Initial Commiss")

    if commission:
        m = re.search(r"[\d,]+\.\d{2,4}", commission)

        if m:
            data["commission_amount"] = clean_amount(m.group())

    if not data.get("commission_amount"):
        for i, line in enumerate(lines):

            if "INITIAL COMMISS" in line.upper():

                nearby_text = " ".join(lines[i:i + 4])

                m = re.search(r"[\d,]+\.\d{2,4}", nearby_text)

                if m:
                    data["commission_amount"] = clean_amount(m.group())

                break

    if not data.get("commission_amount"):
        m = re.search(
            r"Initial\s+Commiss\w*\s+([\d,]+\.\d{2,4})",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["commission_amount"] = clean_amount(m.group(1))

    # ---------------------------------------------------
    # VAT RATE
    # ---------------------------------------------------

    vat_rate = get_next_value(lines, "Tax Rate")

    if vat_rate:
        m = re.search(r"\d+(?:\.\d+)?", vat_rate)
        if m:
            data["vat_rate"] = m.group()

    if not data.get("vat_rate"):
        m = re.search(r"Tax Rate\s*%\s+(\d+(?:\.\d+)?)", compact_text, re.IGNORECASE)

        if m:
            data["vat_rate"] = m.group(1)

    # ---------------------------------------------------
    # VAT AMOUNT
    # ---------------------------------------------------

    vat_amount = get_next_value(lines, "Taxe Value")

    if vat_amount:
        m = re.search(r"[\d,]+\.\d{2,4}", vat_amount)

        if m:
            data["vat_amount"] = clean_amount(m.group())

    if not data.get("vat_amount"):
        m = re.search(r"Taxe Value\s+([\d,]+\.\d{2,4})", compact_text, re.IGNORECASE)

        if m:
            data["vat_amount"] = clean_amount(m.group(1))

    # ---------------------------------------------------
    # TOTAL AMOUNT
    # ---------------------------------------------------

    for i, line in enumerate(lines):

        if "COMMISSION" in line.upper() and "VAT" in line.upper():

            nearby_text = " ".join(lines[i:i + 4])

            m = re.search(r"[\d,]+\.\d{2,4}", nearby_text)

            if m:
                data["total_amount"] = clean_amount(m.group())

            break

    if not data.get("total_amount"):
        m = re.search(
            r"Commission\s+with VAT\s+([\d,]+\.\d{2,4})",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["total_amount"] = clean_amount(m.group(1))

    # ---------------------------------------------------
    # COMMISSION ITEMS
    # ---------------------------------------------------

    data["commission_items"] = []

    if data.get("commission_amount"):
        data["commission_items"].append({
            "commission_type": "commission",
            "commission_percentage": None,
            "commission_amount": data["commission_amount"],
        })

    return data






# import re
# from datetime import datetime
# from .utils import clean_lines, clean_amount


# def normalize_arabia_date(value):
#     try:
#         return datetime.strptime(value.strip(), "%d-%b-%y").strftime("%Y-%m-%d")
#     except Exception:
#         return value


# def parse_arabia_credit_note(raw_text):
#     data = {}

#     lines = clean_lines(raw_text)
#     compact_text = " ".join(lines)
#     upper_text = compact_text.upper()

#     data["document_type"] = (
#         "TAX CREDIT NOTE"
#         if "TAX INVOICE RAISED BY BUYER" in upper_text
#         else None
#     )

#     data["company_name"] = (
#         "ARABIA INSURANCE CO. S.A.L."
#         if "ARABIA INSURANCE" in upper_text
#         else None
#     )

#     data["is_arabia"] = "ARABIA INSURANCE" in upper_text

#     m = re.search(r"TRN\s*:?\s*(\d{15})", compact_text, re.IGNORECASE)
#     if m:
#         data["tax_registration_number"] = m.group(1)

#     m = re.search(r"\bTCN/[A-Z]+/\d{4}/\d+\b", compact_text)
#     if m:
#         data["invoice_number"] = m.group()

#     m = re.search(r"\b\d{2}-[A-Z]{3}-\d{2}\b", compact_text, re.IGNORECASE)
#     if m:
#         data["invoice_date"] = normalize_arabia_date(m.group())

#     m = re.search(r"Bill by:\s*(.+?)\s+Address:", compact_text, re.IGNORECASE)
#     if m:
#         broker = m.group(1).replace("L L C", "").replace("LLC", "").strip()
#         data["broker_name"] = broker

#     data["is_promise_broker"] = (
#         "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
#     )

#     data["broker_validation"] = (
#         "VALID" if data["is_promise_broker"] else "NON_PROMISE_BROKER"
#     )

#     m = re.search(r"Producer TAX Reg:\s*(\d{15})", compact_text, re.IGNORECASE)
#     if m:
#         data["broker_tax_registration_number"] = m.group(1)

#     m = re.search(r"Branch\s+Department\s+(.+?)\s+Motor Insurance", compact_text, re.IGNORECASE)
#     if m:
#         data["branch"] = m.group(1).strip()
#     elif "UNITED ARAB EMIRATES" in upper_text:
#         data["branch"] = "United Arab Emirates"

#     if "MOTOR INSURANCE" in upper_text:
#         data["department"] = "Motor Insurance"
#         data["policy_type"] = "Motor Insurance"

#     m = re.search(r"Policy No\s+([A-Z]+/[A-Z]+/\d{4}/\d+)", compact_text, re.IGNORECASE)
#     if m:
#         data["policy_number"] = m.group(1)

#     if "AED" in upper_text:
#         data["currency"] = "AED"

#     m = re.search(r"Initial Commission\s+([\d,]+\.\d{2})", compact_text, re.IGNORECASE)
#     if m:
#         data["commission_amount"] = clean_amount(m.group(1))

#     m = re.search(r"Tax Rate\s*%\s+(\d+(?:\.\d+)?)", compact_text, re.IGNORECASE)
#     if m:
#         data["vat_rate"] = m.group(1)

#     m = re.search(r"Taxe Value\s+([\d,]+\.\d{2,3})", compact_text, re.IGNORECASE)
#     if m:
#         data["vat_amount"] = clean_amount(m.group(1))

#     m = re.search(r"Commission\s+with VAT\s+([\d,]+\.\d{2,4})", compact_text, re.IGNORECASE)
#     if m:
#         data["total_amount"] = clean_amount(m.group(1))

#     data["commission_items"] = []

#     if data.get("commission_amount"):
#         data["commission_items"].append({
#             "commission_type": "commission",
#             "commission_percentage": None,
#             "commission_amount": data["commission_amount"],
#         })

#     return data