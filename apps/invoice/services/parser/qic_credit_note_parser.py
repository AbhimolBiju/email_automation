import re
from datetime import datetime
from .utils import clean_lines, normalize_date, clean_amount, is_amount


def normalize_qic_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(value.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return value


def parse_qic_credit_note(raw_text):
    data = {}

    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
    upper_text = compact_text.upper()

    # Basic fields
    data["document_type"] = (
        "CREDIT NOTE"
        if "CREDIT NOTE" in upper_text
        else None
    )

    data["company_name"] = (
        "QATAR INSURANCE COMPANY"
        if "QIC" in upper_text
        else None
    )

    data["is_qic"] = "QIC" in upper_text

    # ---------------------------------------------------
    # ACCOUNT NO, DOC NO, DATE, BRANCH, DEPARTMENT, PRODUCT
    # Line-by-line first
    # ---------------------------------------------------


    def is_qic_noise(value):
        value = (value or "").strip()
        return value in ["", ":", ".", "..", ". ."]


    def get_next_clean_value(lines, label, pattern=None, lookahead=8):
        label_upper = label.upper()

        for i, line in enumerate(lines):
            if line.upper().strip() == label_upper:
                for nxt in lines[i + 1:i + 1 + lookahead]:
                    cleaned = nxt.replace(":", "").strip()

                    if is_qic_noise(cleaned):
                        continue

                    if pattern:
                        m = re.search(pattern, cleaned, re.IGNORECASE)

                        if m:
                            return m.group()

                    else:
                        return cleaned

        return None


    # Line-by-line extraction
    account_no = get_next_clean_value(lines, "Account No.", r"\d{5,}")
    if account_no:
        data["account_number"] = account_no

    doc_no = get_next_clean_value(lines, "Doc No.", r"\d{3}\s*-\s*\d{5,6}")
    if doc_no:
        data["invoice_number"] = doc_no.replace(" ", "")

    date_value = get_next_clean_value(lines, "Date", r"\d{2}/\d{2}/\d{4}")
    if date_value:
       data["invoice_date"] = normalize_date(date_value)

    branch = get_next_clean_value(lines, "Branch")
    if branch:
        data["branch"] = branch

    department = get_next_clean_value(lines, "Department")
    if department:
        data["department"] = department

    product = get_next_clean_value(lines, "Product")
    if product:
        data["policy_type"] = product


    # Regex fallbacks
    if not data.get("account_number"):
        m = re.search(
            r"Account No\.?\s*:?\s*(?:[:.\s]*)?(\d{5,})",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["account_number"] = m.group(1)

    if not data.get("invoice_number"):
        m = re.search(
            r"Doc No\.?\s*:?\s*(?:[:.\s]*)?(\d{3}\s*-\s*\d{5,6})",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["invoice_number"] = m.group(1).replace(" ", "")

    if not data.get("invoice_number"):
        m = re.search(r"\b\d{3}\s*-\s*\d{5,6}\b", compact_text)

        if m:
            data["invoice_number"] = m.group().replace(" ", "")

    if not data.get("invoice_date"):
        m = re.search(
            r"Date\s*:?\s*(?:[:.\s]*)?(\d{2}/\d{2}/\d{4})",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["invoice_date"] = normalize_date(m.group(1))

    if not data.get("invoice_date"):
        m = re.search(r"\b\d{2}/\d{2}/\d{4}\b", compact_text)

        if m:
            data["invoice_date"] = normalize_date(m.group())

    if not data.get("branch"):
        m = re.search(
            r"Branch\s*:?\s*(?:[:.\s]*)?"
            r"(Abudhabi|Abu Dhabi|Dubai Branch|Dubai|Sharjah|Ajman|Fujairah|Ras Al Khaimah)",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["branch"] = m.group(1)

    if not data.get("department"):
        m = re.search(
            r"Department\s*:?\s*(?:[:.\s]*)?(Retail|Motor|Commercial)",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["department"] = m.group(1)

    if not data.get("department") and "RETAIL" in upper_text:
        data["department"] = "Retail"

    if (
        not data.get("policy_type")
        or data.get("policy_type") in [".", "..", ". ."]
        ):
        m = re.search(
            r"Product\s*:?\s*(?:[:.\s]*)?"
            r"(TP\s*\+\s*Own Damage|Third Party Liability|Comprehensive)",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["policy_type"] = m.group(1)

    if (
        not data.get("policy_type")
        or data.get("policy_type") in [".", "..", ". ."]
        ):
        m = re.search(
            r"(TP\s*\+\s*Own Damage|Third Party Liability|Comprehensive)",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["policy_type"] = m.group(1)


    # ---------------------------------------------------
    # BROKER NAME
    # ---------------------------------------------------

    for line in lines:
        if "PROMISE INSURANCE SERVICES" in line.upper():
            broker = line.replace("To:", "").replace("L.L.C.", "").replace("LLC", "").strip()
            data["broker_name"] = broker
            break

    if not data.get("broker_name"):
        m = re.search(
            r"(PROMISE\s+INSURANCE\s+SERVICES)\s*(?:L\.?L\.?C\.?|LLC)?",
            compact_text,
            re.IGNORECASE,
        )
        if m:
            data["broker_name"] = m.group(1).strip()

    data["is_promise_broker"] = (
        "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
    )

    # ---------------------------------------------------
    # INSURED
    # ---------------------------------------------------

    for line in lines:
        if "INSURED" in line.upper():
            if ":" in line:
                insured = line.split(":", 1)[1].strip()
                if insured:
                    data["insured_name"] = insured
                    break

    if not data.get("insured_name"):
        m = re.search(r"Insured\s*:?\s*(.+?)\s+Regn No", compact_text, re.IGNORECASE)
        if m:
            data["insured_name"] = m.group(1).strip()

    # ---------------------------------------------------
    # POLICY NUMBER
    # ---------------------------------------------------

    for line in lines:
        if "POLICY NO" in line.upper():
            m = re.search(r"\d{6,}", line)
            if m:
                data["policy_number"] = m.group()
                break

    if not data.get("policy_number"):
        m = re.search(r"Policy No\.?\s*:?\s*(\d+)", compact_text, re.IGNORECASE)
        if m:
            data["policy_number"] = m.group(1)

    # ---------------------------------------------------
    # POLICY PERIOD
    # ---------------------------------------------------

    for i,line in enumerate(lines):
        if "POLICY PERIOD" in line.upper():

            nearby_text = " ".join(lines[i:i + 5])

            m = re.search(
                r"(\d{2}-[A-Za-z]{3}-\d{4}).*?To\s+(\d{2}-[A-Za-z]{3}-\d{4})",
                nearby_text,
                re.IGNORECASE,
            )

            if m:
                data["policy_start_date"] = normalize_qic_date(m.group(1))
                data["policy_end_date"] = normalize_qic_date(m.group(2))
            break

    if not data.get("policy_start_date"):
        m = re.search(
            r"Policy Period\s+(\d{2}-[A-Za-z]{3}-\d{4}).*?To\s+(\d{2}-[A-Za-z]{3}-\d{4})",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["policy_start_date"] = normalize_qic_date(m.group(1))
            data["policy_end_date"] = normalize_qic_date(m.group(2))
    # ---------------------------------------------------
    # COMMISSION / VAT / TOTAL
    # ---------------------------------------------------
    commission_items = []

    def clean_qic_amount(value):
        if not value:
            return None

        value = value.replace(",", "").strip()

        # QIC sometimes gives VAT as ".00"
        if value.startswith("."):
            value = "0" + value

        return clean_amount(value)


    AMOUNT_RE = r"(?:\d+(?:,\d{3})*|\d*)\.\d{2}"

    for i, line in enumerate(lines):
        if "BROKERAGE" in line.upper():
            percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)

            commission_percentage = (
                percent_match.group(1)
                if percent_match
                else None
                )

            nearby_text = " ".join(lines[i:i + 15])

            amounts = re.findall(AMOUNT_RE, nearby_text)

        # Example:
        # 1,244.20 1,244.20 0.00 .00 1,244.20
            if len(amounts) >= 5:
                data["commission_percentage"] = commission_percentage
                data["commission_amount"] = clean_qic_amount(amounts[0])
                data["taxable_amount"] = clean_qic_amount(amounts[1])
                data["vat_rate"] = clean_qic_amount(amounts[2])
                data["vat_amount"] = clean_qic_amount(amounts[3])
                data["total_amount"] = clean_qic_amount(amounts[4])

            elif len(amounts) >= 3:
                data["commission_percentage"] = commission_percentage
                data["commission_amount"] = clean_qic_amount(amounts[0])
                data["vat_amount"] = clean_qic_amount(amounts[-2])
                data["total_amount"] = clean_qic_amount(amounts[-1])

            if data.get("commission_amount"):
                commission_items.append({
                    "commission_type": "brokerage",
                    "commission_percentage": data.get("commission_percentage"),
                    "commission_amount": data.get("commission_amount"),
                    })

            break


    # Regex fallback for brokerage row
    if not data.get("commission_amount"):
        m = re.search(
            r"Brokerage\s*@\s*(\d+(?:\.\d+)?)\s*%(.+?)TOTAL",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["commission_percentage"] = m.group(1)

            amounts = re.findall(AMOUNT_RE, m.group(2))

            if len(amounts) >= 5:
                data["commission_amount"] = clean_qic_amount(amounts[0])
                data["taxable_amount"] = clean_qic_amount(amounts[1])
                data["vat_rate"] = clean_qic_amount(amounts[2])
                data["vat_amount"] = clean_qic_amount(amounts[3])
                data["total_amount"] = clean_qic_amount(amounts[4])

            elif len(amounts) >= 3:
                data["commission_amount"] = clean_qic_amount(amounts[0])
                data["vat_amount"] = clean_qic_amount(amounts[-2])
                data["total_amount"] = clean_qic_amount(amounts[-1])

            if data.get("commission_amount"):
                commission_items.append({
                    "commission_type": "brokerage",
                    "commission_percentage": data.get("commission_percentage"),
                    "commission_amount": data.get("commission_amount"),
                    })

    data["commission_items"] = commission_items

    return data