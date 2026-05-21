import re
from .utils import clean_lines, normalize_date, clean_amount, get_value_after_label, is_amount


POLICY_RE = r"\d{4}/\d{2}/\d/\d{2}"


def parse_alliance_credit_note(raw_text):

    data = {}

    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
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
        "ALLIANCE INSURANCE"
        if "ALLIANCE" in upper_text
        else None
    )

    data["is_alliance"] = (
        True
        if "ALLIANCE" in upper_text
        else False
    )

    # ---------------------------------------------------
    # INVOICE NUMBER
    # ---------------------------------------------------
    m = re.search(
        r"\b(?:INV|INVC)\d+/\d{4}\b",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["invoice_number"] = m.group()


    # ---------------------------------------------------
    # INVOICE DATE
    # ---------------------------------------------------

    for i, line in enumerate(lines):

        if line.upper().strip() == "DATE":

            for nxt in lines[i + 1:i + 5]:

                m = re.search(r"\d{2}[./-]\d{2}[./-]\d{4}", nxt)

                if m:
                    data["invoice_date"] = normalize_date(m.group())
                    break

            break

    if not data.get("invoice_date"):

        dates = re.findall(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", compact_text)

        if dates:
            data["invoice_date"] = normalize_date(dates[0])


    # ---------------------------------------------------
    # BROKER NAME
    # ---------------------------------------------------

    m = re.search(
        r"(?:Agent/Broker|Account Holder|Broker/Agent)\s*:?\s*(PROMISE\s+INSURANCE\s+SERVICES)(?:\s+L\.?L\.?C\.?| LLC)?",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["broker_name"] = m.group(1).strip()

    data["is_promise_broker"] = (
        "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
    )


    # ---------------------------------------------------
    # PROMISE BROKER CHECK
    # ---------------------------------------------------

    broker = data.get("broker_name", "")

    data["is_promise_broker"] = (
        True
        if "PROMISE INSURANCE SERVICES" in broker.upper()
        else False
    )   


    # ---------------------------------------------------
    # BRANCH
    # ---------------------------------------------------

    branch = get_value_after_label(lines, "Branch")

    if branch:
        data["branch"] = branch

    # ---------------------------------------------------
    # ACCOUNT NUMBER
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if "AGENT/BROKER" in line.upper():
            for prev in reversed(lines[max(0, i - 6):i]):
                cleaned = prev.strip()

                if re.fullmatch(r"\d{8,15}", cleaned):
                    data["account_number"] = cleaned
                    break

            break

    # fallback from compact text
    if not data.get("account_number"):
        m = re.search(
            r"Customer ID\s*:?\s*\d+\s+(\d{8,15})\s+Agent/Broker",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["account_number"] = m.group(1)


    # ---------------------------------------------------
    # INSURED NAME
    # ---------------------------------------------------

    m = re.search(
        r"Insured\s*:?\s*(.+?)\s+Address",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        insured_name = re.sub(r"\s+", " ", m.group(1)).strip()
        # remove Mr / Mrs / Ms / Miss if present
        insured_name = re.sub(
            r"^(MR|MRS|MS|MISS)\.?\s+",
            "",
            insured_name,
            flags=re.IGNORECASE,
        )

        data["insured_name"] = insured_name


    if not data.get("insured_name"):
        m = re.search(
            r"Insured Name\s*:?\s*(.+?)\s+Premium",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            insured_name = re.sub(r"\s+", " ", m.group(1)).strip()

            insured_name = re.sub(
                r"^(MR|MRS|MS|MISS)\.?\s+",
                "",
                insured_name,
                flags=re.IGNORECASE,
            )

            data["insured_name"] = insured_name


    # ---------------------------------------------------
    # POLICY NUMBER
    # ---------------------------------------------------

    m = re.search(
        r"Policy No\.?\s*[:/]?\s*Year\s*:?\s*(\d+)",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_number"] = m.group(1)

    if not data.get("policy_number"):
        m = re.search(
            r"Policy No\.?\s+(\d{4}/\d{2}/\d/\d{2})",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["policy_number"] = m.group(1)


    # ---------------------------------------------------
    # POLICY TYPE
    # ---------------------------------------------------

    policy_type = get_value_after_label(lines, "Policy Type")

    if policy_type:
        data["policy_type"] = policy_type

    # ---------------------------------------------------
    # POLICY DATES
    # ---------------------------------------------------

    m = re.search(
        r"Period of Cover\s*:\s*From\s+(\d{2}[./-]\d{2}[./-]\d{4})\s+To\s+(\d{2}[./-]\d{2}[./-]\d{4})",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_start_date"] = normalize_date(m.group(1))
        data["policy_end_date"] = normalize_date(m.group(2))

    # ---------------------------------------------------
    # COMMISSION
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

            amount_match = re.search(r"([\d,]+\.\d{2})$", line)

            if amount_match:
                amount = clean_amount(amount_match.group(1))
            else:
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
    # TOTAL AMOUNT
    # ---------------------------------------------------


    m = re.search(
        r"Total Amount\s*:?\s*([\d,]+\.\d{2})",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["total_amount"] = clean_amount(m.group(1))

    if not data.get("total_amount"):
        m = re.search(
            r"Total:.*?([\d,]+\.\d{2})",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["total_amount"] = clean_amount(m.group(1))

    if not data.get("total_amount") and data.get("commission_amount"):
        data["total_amount"] = data["commission_amount"]



    # ---------------------------------------------------
    # NET AMOUNT
    # ---------------------------------------------------

    net_amount = get_value_after_label(lines, "Net Amount")

    if net_amount:

        m = re.search(r"([\d,]+\.\d{2})", net_amount)

        if m:
            data["net_amount"] = clean_amount(m.group(1))


    # ---------------------------------------------------
    # TRN
    # ---------------------------------------------------

    trn_values = re.findall(r"\b\d{15}\b", compact_text)

    if trn_values:

        data["tax_registration_number"] = trn_values[-1]

    return data