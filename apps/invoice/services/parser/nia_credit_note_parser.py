import re
from .utils import clean_lines, normalize_date, clean_amount, is_amount


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


def parse_nia_credit_note(raw_text):
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

    data["company_name"] = "THE NEW INDIA ASSURANCE CO. LTD"

    data["is_nia"] = (
        "NEW INDIA ASSURANCE" in upper_text
        or "NIA" in upper_text
        or "ADSA" in upper_text
        or "RHS" in upper_text
    )

    data["is_nia_auh"] = (
        "ABU DHABI SHIPPING AGENCY" in upper_text
        or "ADSA" in upper_text
    )

    data["is_nia_dxb"] = (
        "RAIS HASSAN SAADI" in upper_text
        or "RHS" in upper_text
    )

    # ---------------------------------------------------
    # BROKER NAME
    # ---------------------------------------------------

    name = get_next_value(lines, "Name")

    if name:
        broker_name = (
            name.replace("L.L.C.", "")
            .replace("LLC", "")
            .replace("- ONLINE MOTOR", "")
            .strip()
        )
        data["broker_name"] = broker_name

    if not data.get("broker_name"):
        m = re.search(
            r"(PROMISE\s+INSURANCE\s+SERVICES).*?(?:Emirate|Address|Voucher)",
            compact_text,
            re.IGNORECASE,
        )
        if m:
            broker_name = (
                m.group(1)
                .replace("L.L.C.", "")
                .replace("LLC", "")
                .strip()
            )
            data["broker_name"] = broker_name
    
    data["is_promise_broker"] = (
        "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
        )

    # ---------------------------------------------------
    # BROKER VALIDATION
    # ---------------------------------------------------

    data["broker_validation"] = (
        "VALID"
        if data.get("is_promise_broker")
        else "NON_PROMISE_BROKER"
    )

    # ---------------------------------------------------
    # CLIENT TRN / BROKER TRN
    # ---------------------------------------------------

    m = re.search(r"Client TRN\s+(\d{15})", compact_text, re.IGNORECASE)
    if m:
        data["broker_tax_registration_number"] = m.group(1)

    # ---------------------------------------------------
    # VOUCHER / INVOICE NUMBER
    # ---------------------------------------------------

    voucher = get_next_value(lines, "Voucher No")

    if voucher:
        data["invoice_number"] = voucher

    if not data.get("invoice_number"):
        m = re.search(r"Voucher No\s+([A-Z0-9\-]+)", compact_text, re.IGNORECASE)
        if m:
            data["invoice_number"] = m.group(1)

    # DXB fallback: long voucher number
    if not data.get("invoice_number"):
        m = re.search(r"\b\d{10,}[A-Z]\b", compact_text)
        if m:
            data["invoice_number"] = m.group()

    # ---------------------------------------------------
    # INVOICE DATE
    # ---------------------------------------------------

    date_value = get_next_value(lines, "Date")

    if date_value:
        m = re.search(r"\d{2}[./-]\d{2}[./-]\d{4}", date_value)
        if m:
            data["invoice_date"] = normalize_date(m.group())

    if not data.get("invoice_date"):
        m = re.search(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", compact_text)
        if m:
            data["invoice_date"] = normalize_date(m.group())

    # ---------------------------------------------------
    # INSURED NAME
    # ---------------------------------------------------

    for i, line in enumerate(lines):

        if line.upper().strip() == "INSURED":

            insured_parts = []

            for nxt in lines[i + 1:i + 8]:

                cleaned = nxt.strip()
                upper = cleaned.upper()

                if (
                    "COMMISSION" in upper
                    or "POLICY TYPE" in upper
                    or "GAIUSASSING" in upper
                    or "%" in cleaned
                    or re.search(r"\d+\.\d{2}", cleaned)
                ):
                    break

                if upper == "POLICY NO":
                    continue

                if cleaned:
                    insured_parts.append(cleaned)

            if insured_parts:
                data["insured_name"] = " ".join(insured_parts)

            break

    # regex fallback
    if not data.get("insured_name"):

        m = re.search(
            r"Insured\s+(.+?)\s+Policy No",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["insured_name"] = m.group(1).strip()

    # ---------------------------------------------------
    # POLICY NUMBER
    # ---------------------------------------------------

   
    m = re.search(r"\b\d{3}/[A-Z]/\d+\b", compact_text)

    if m:
        data["policy_number"] = m.group()

    m = re.search(
        r"Policy No\s+([A-Z0-9/]+)",
        compact_text,
        re.IGNORECASE,
        )

    if m and not data.get("policy_number"):
        candidate = m.group(1).strip()

        if "/" in candidate and re.search(r"\d", candidate):
            data["policy_number"] = candidate

    # m = re.search(
    #     r"Policy No\s+([A-Z0-9/]+)",
    #     compact_text,
    #     re.IGNORECASE,
    # )

    # if m:
    #     candidate = m.group(1).strip()
    #     if "/" in candidate and re.search(r"\d", candidate):
    #         data["policy_number"] = candidate

    # if not data.get("policy_number"):
    #     m = re.search(r"\b\d{3}/[A-Z]/\d+\b", compact_text)

    #     if m:
    #         data["policy_number"] = m.group()

    # ---------------------------------------------------
    # POLICY TYPE
    # ---------------------------------------------------

    m = re.search(
        r"Policy Type\s+(.+?)\s+(?:Premium|Policy Period|Period)",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_type"] = m.group(1).strip()

    # ---------------------------------------------------
    # POLICY PERIOD
    # ---------------------------------------------------

    m = re.search(
        r"(?:Policy Period|Period)\s+(\d{2}[./-]\d{2}[./-]\d{4})\s+(?:TO|-)\s+(\d{2}[./-]\d{2}[./-]\d{4})",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_start_date"] = normalize_date(m.group(1))
        data["policy_end_date"] = normalize_date(m.group(2))

    # ---------------------------------------------------
    # PREMIUM
    # ---------------------------------------------------

    m = re.search(r"Premium\s+([\d,]+\.\d{2})", compact_text, re.IGNORECASE)
    if m:
        data["premium_amount"] = clean_amount(m.group(1))


    # ---------------------------------------------------
    # COMMISSION / VAT / TOTAL
    # ---------------------------------------------------

    commission_items = []

    for i, line in enumerate(lines):
        if line.upper().strip() == "COMMISSION":
            nearby_text = " ".join(lines[i:i + 8])

            amounts = re.findall(
                r"\b\d+(?:,\d{3})*\.\d{2}\b",
                nearby_text
                )

            percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", nearby_text)

            if percent_match:
                data["commission_percentage"] = percent_match.group(1)

            if data.get("is_nia_dxb") and len(amounts) >= 4:
                data["commission_amount"] = clean_amount(amounts[0])
                data["vat_rate"] = clean_amount(amounts[1])
                data["vat_amount"] = clean_amount(amounts[2])
                data["total_amount"] = clean_amount(amounts[3])

            elif len(amounts) >= 3:
                data["commission_amount"] = clean_amount(amounts[0])
                data["vat_amount"] = clean_amount(amounts[1])
                data["total_amount"] = clean_amount(amounts[2])

            break

# AUH fallback: Commission, 15 %, amount, 5%, vat, net
    if not data.get("commission_amount"):
        m = re.search(
            r"Commission\s+(\d+(?:\.\d+)?)\s*%\s+([\d,]+\.\d{2})\s+5%\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["commission_percentage"] = m.group(1)
            data["commission_amount"] = clean_amount(m.group(2))
            data["vat_amount"] = clean_amount(m.group(3))
            data["total_amount"] = clean_amount(m.group(4))

    # DXB fallback: Commission amount vat_rate vat total
    if not data.get("commission_amount"):
        m = re.search(
            r"Commission\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["commission_amount"] = clean_amount(m.group(1))
            data["vat_rate"] = clean_amount(m.group(2))
            data["vat_amount"] = clean_amount(m.group(3))
            data["total_amount"] = clean_amount(m.group(4))

    if data.get("commission_amount"):
        commission_items.append({
            "commission_type": "commission",
            "commission_percentage": data.get("commission_percentage"),
            "commission_amount": data.get("commission_amount"),
            })

    data["commission_items"] = commission_items

    

    # commission_items = []

    # for i, line in enumerate(lines):

    #     if line.upper().strip() == "COMMISSION":

    #         nearby_lines = lines[i:i + 10]

    #         nearby_text = " ".join(nearby_lines)

    #         # Commission %
    #         percent_match = re.search(
    #             r"(\d+(?:\.\d+)?)\s*%",
    #             nearby_text
    #         )

    #         if percent_match:
    #             data["commission_percentage"] = percent_match.group(1)

    #         amounts = re.findall(
    #             r"\b\d+(?:,\d{3})*\.\d{2}\b",
    #             nearby_text
    #         )

    #         if len(amounts) >= 3:

    #             data["commission_amount"] = clean_amount(amounts[0])
    #             data["vat_amount"] = clean_amount(amounts[1])
    #             data["total_amount"] = clean_amount(amounts[2])

    #         break

    # # fallback from TOTAL row
    # if not data.get("total_amount"):

    #     for i, line in enumerate(lines):

    #         if "NET COMMISSION" in line.upper():

    #             nearby_text = " ".join(lines[i:i + 5])

    #             amounts = re.findall(
    #                 r"\b\d+(?:,\d{3})*\.\d{2}\b",
    #                 nearby_text
    #             )

    #             if amounts:
    #                 data["total_amount"] = clean_amount(amounts[-1])

    #             break

    # # commission items
    # if data.get("commission_amount"):

    #     commission_items.append({
    #         "commission_type": "commission",
    #         "commission_percentage": data.get("commission_percentage"),
    #         "commission_amount": data.get("commission_amount"),
    #     })

    # data["commission_items"] = commission_items


    # ---------------------------------------------------
    # AGENT TRN
    # ---------------------------------------------------

    m = re.search(r"(?:ADSA TRN|RHS INS TRN)\s*:?\s*(\d{15})", compact_text, re.IGNORECASE)
    if m:
        data["tax_registration_number"] = m.group(1)

    return data