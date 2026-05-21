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

    value = value.strip()
    value = re.sub(r"[.\-]", "/", value)

    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def extract_policy_date_range(text):
    if not text:
        return None, None

    m = re.search(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        text,
        re.IGNORECASE
    )

    if m:
        return normalize_date(m.group(1)), normalize_date(m.group(2))

    return None, None


def is_valid_policy(value):
    if not value:
        return False

    value = value.strip().upper()

    if re.search(r"(DATE|VAT|TOTAL|PREMIUM|BROKER|INVOICE)", value):
        return False

    if len(value) < 6:
        return False

    if not re.search(r"\d", value):
        return False

    return True


def parse_alliance_debit_note(text, tables=None):
    data = {}

    lines = clean_lines(text)
    compact_text = re.sub(r"\s+", " ", text)
    upper_text = compact_text.upper()

    # Basic fields
    data["document_type"] = (
        "DEBIT NOTE"
        if "DEBIT NOTE" in upper_text
        else "TAX INVOICE" if "TAX INVOICE" in upper_text
        else None
    )

    data["insurer_name"] = (
        "ALLIANCE INSURANCE"
        if "ALLIANCE" in upper_text
        else None
    )

    data["premium_currency"] = "AED"

    # Invoice / debit note number
    patterns = [
        r"Ref\.?\s*Invoice\s*#\s*([A-Z0-9/\-]+)",
        r"Invoice\s*Ref\.?\s*No\.?\s*:?\s*([A-Z0-9/\-]+)",
        r"Invoice\s*No\.?\s*:?\s*([A-Z0-9/\-]+)",
        r"Tax\s*Invoice\s*No\.?\s*:?\s*([A-Z0-9/\-]+)",
        r"Debit\s*Note\s*No\.?\s*:?\s*([A-Z0-9/\-]+)",
        r"Document\s*No\.?\s*:?\s*([A-Z0-9/\-]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            data["invoice_number"] = m.group(1).strip()
            break

    # Invoice date
    patterns = [
        r"Invoice\s*Date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Debit\s*Note\s*Date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            data["invoice_date"] = normalize_date(m.group(1))
            break

    # Insured name

    # Priority 1: full MR name line
    m = re.search(
        r"Mr\.?\s+([A-Z][A-Z\s]+)",
        compact_text,
        re.IGNORECASE
    )

    if m:
        insured_name = re.sub(
            r"\s+",
            " ",
            m.group(1)
        ).strip()

        insured_name = re.split(
            r"(Insured|Address|Date|Dept|Department)",
            insured_name,
            flags=re.IGNORECASE
        )[0].strip()

        if len(insured_name) > 5:
            data["insured_name"] = insured_name

    # Priority 2: standard insured extraction
    if not data.get("insured_name"):

        patterns = [
            r"Insured\s*:?\s*([^\n\r]+)",
            r"Customer\s*Name\s*:?\s*([^\n\r]+)",
            r"Name\s*of\s*Insured\s*:?\s*([^\n\r]+)",
        ]

        for pattern in patterns:

            m = re.search(pattern, text, re.IGNORECASE)

            if m:
                value = re.sub(
                    r"\s+",
                    " ",
                    m.group(1)
                ).strip(" :-")

                if len(value) > 2:
                    data["insured_name"] = value
                    break


    # Broker name

    # Priority 1: Promise Insurance multiline extraction
    m = re.search(
        r"(Promise\s+Insurance\s+Services\s+L\.?L\.?C\.?)",
        compact_text,
        re.IGNORECASE
    )

    if m:
        data["broker_name"] = re.sub(
            r"\s+",
            " ",
            m.group(1)
        ).strip()

    # Priority 2: Agent/Broker labels
    if not data.get("broker_name"):

        patterns = [
            r"Agent/Broker\s*:?\s*([^\n\r]+)",
            r"Account\s*Holder\s*:?\s*([^\n\r]+)",
            r"Broker\s*Name\s*:?\s*([^\n\r]+)",
            r"Broker\s*:?\s*([^\n\r]+)",
            r"Agent\s*:?\s*([^\n\r]+)",
        ]

        for pattern in patterns:

            m = re.search(pattern, text, re.IGNORECASE)

            if m:

                broker_name = re.sub(
                    r"\s+",
                    " ",
                    m.group(1)
                ).strip(" :-")

                broker_name = re.split(
                    r"(TRN|Address|Department|Date|Policy|Unit)",
                    broker_name,
                    flags=re.IGNORECASE
                )[0].strip()

                if len(broker_name) > 3:
                    data["broker_name"] = broker_name
                    break

    broker_name = data.get("broker_name", "")

    data["is_promise_broker"] = (
        "PROMISE" in broker_name.upper()
    )


    # Policy number
    # Priority 1: actual Policy No from description
    m = re.search(
        r"Policy\s*No\.?\s*([A-Z0-9\/\-]+)",
        compact_text,
        re.IGNORECASE
    )

    if m:
        value = m.group(1).strip()
        if is_valid_policy(value):
            data["policy_number"] = value

    # Priority 2: Policy No / Year
    if not data.get("policy_number"):
        m = re.search(
            r"Policy\s*No\.?\s*/?\s*Year\s*:?\s*([A-Z0-9\/\-]+)",
            compact_text,
            re.IGNORECASE
        )

        if m:
            value = m.group(1).strip()
            if is_valid_policy(value):
                data["policy_number"] = value

    # Priority 3: Policy Number
    if not data.get("policy_number"):
        m = re.search(
            r"Policy\s*Number\s*:?\s*([A-Z0-9\/\-]+)",
            compact_text,
            re.IGNORECASE
        )

        if m:
            value = m.group(1).strip()
            if is_valid_policy(value):
                data["policy_number"] = value

    # Priority 4: Ref Policy only as fallback
    if not data.get("policy_number"):
        m = re.search(
            r"Ref\.?\s*Policy\s*#\s*([A-Z0-9\/\-]+)",
            compact_text,
            re.IGNORECASE
        )

        if m:
            value = m.group(1).strip()
            if is_valid_policy(value):
                data["policy_number"] = value

    # Policy type
    patterns = [
        r"Policy\s*Type\s*:?\s*([^\n\r]+)",
        r"Policy\s*Class\s*:?\s*([^\n\r]+)",
        r"Class\s*:?\s*([^\n\r]+)",
        r"Insurance\s*Type\s*:?\s*([^\n\r]+)",
        r"Dept\s*:?\s*([^\n\r]+)",
        r"Department\s*:?\s*([^\n\r]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            value = re.split(
                r"(Discount|Period|Vehicle|Description|Address|Agent|Unit)",
                value,
                flags=re.IGNORECASE
            )[0].strip(" :-")
            value = re.sub(r"\s+", " ", value).strip()

            if value and not re.search(r"\d{4,}", value):
                data["policy_type"] = value
                break

    # Policy period
    for i, line in enumerate(lines):
        if re.search(
            r"(policy\s*period|period\s*of\s*insurance|period\s*of\s*cover)",
            line,
            re.IGNORECASE
        ):
            block = " ".join(lines[i:i + 6])
            start_date, end_date = extract_policy_date_range(block)

            if start_date and end_date and start_date != end_date:
                data["policy_start_date"] = start_date
                data["policy_end_date"] = end_date
                break

    if not data.get("policy_start_date"):
        start_date, end_date = extract_policy_date_range(compact_text)
        if start_date and end_date and start_date != end_date:
            data["policy_start_date"] = start_date
            data["policy_end_date"] = end_date

    # VAT amount
    m = re.search(
        r"VAT\s*@?\s*5\s*%?\s*:?\s*([\d,]+\.\d{2})",
        text,
        re.IGNORECASE
    )

    if m:
        data["vat_amount"] = clean_amount(m.group(1))

    # Amounts
    numbers = re.findall(r"([\d,]+\.\d{2})", text)
    cleaned_numbers = []

    for number in numbers:
        amount = clean_amount(number)
        if amount is not None:
            cleaned_numbers.append(amount)

    if cleaned_numbers:
        data["total_amount"] = cleaned_numbers[-1]

    if data.get("total_amount") is not None and data.get("vat_amount") is not None:
        data["net_premium"] = round(
            data["total_amount"] - data["vat_amount"],
            2
        )

    # Fallback: calculate VAT if only total exists
    if data.get("total_amount") is not None and data.get("vat_amount") is None:
        data["vat_amount"] = round(data["total_amount"] * 5 / 105, 2)
        data["net_premium"] = round(data["total_amount"] - data["vat_amount"], 2)

    # Mapper compatibility
    data["vat_amount"]=data.get("vat_amount")
    data["net_premium"]=data.get("net_premium")
    data["total"] = data.get("total_amount")
    data["total_premium"] = data.get("total_amount")
    data["net_due"] = data.get("total_amount")

    # Branch
    data["branch"] = None

    return data