import re
from datetime import datetime

POLICY_RE = r"\d{2}/\d{4}/\d{2}[A-Z]/\d+"


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


def get_value_after_label(lines, label, lookahead=4):
    label_lower = label.lower()

    for i, line in enumerate(lines):

        if label_lower in line.lower():

            # same-line value
            if ":" in line:
                value = line.split(":", 1)[1].strip()

                if value:
                    return value

            # next lines
            for nxt in lines[i + 1:i + 1 + lookahead]:
                cleaned = nxt.replace(":", "").strip()

                if cleaned:
                    return cleaned

    return None


def is_amount(line):
    return bool(re.fullmatch(r"[\d,]+\.\d{2}", line.strip()))


def parse_fidelity_credit_note(raw_text):

    data = {}
    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)

    # ---------------------------------------------------
    # BASIC IDENTIFICATION
    # ---------------------------------------------------

    data["document_type"] = (
        "TAX CREDIT NOTE"
        if "TAX CREDIT NOTE" in compact_text.upper()
        else None
    )

    data["company_name"] = (
        "UNITED FIDELITY INSURANCE COMPANY"
        if "UNITED FIDELITY INSURANCE COMPANY" in compact_text.upper()
        else None
    )

    data["is_fidelity"] = (
        True
        if (
            "FIDELITY" in compact_text.upper()
            or "UNITED FIDELITY INSURANCE COMPANY" in compact_text.upper()
        )
        else False
    )

    # ---------------------------------------------------
    # BRANCH
    # ---------------------------------------------------

    for line in lines:
        if line.upper().startswith("BRANCH"):

            branch = line.replace("BRANCH", "").strip()

            if branch:
                data["branch"] = branch

            break

    # ---------------------------------------------------
    # BROKER NAME
    # ---------------------------------------------------

    for line in lines:

        line_upper = line.upper()

        if "INSURANCE SERVICES" in line_upper or "BROKER" in line_upper:

            broker_name = line.strip()
            broker_name = broker_name.replace("L.L.C.", "")
            broker_name = broker_name.replace("LLC", "")
            broker_name = broker_name.strip()

            data["broker_name"] = broker_name
            break

    # fallback using compact text
    if not data.get("broker_name"):

        m = re.search(
            r"(PROMISE\s+INSURANCE\s+SERVICES)\s*(?:L\.?L\.?C\.?|LLC)?",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["broker_name"] = m.group(1).strip()

    # ---------------------------------------------------
    # PROMISE BROKER CONFIRMATION
    # ---------------------------------------------------

    broker_name = data.get("broker_name", "")

    data["is_promise_broker"] = (
        True
        if "PROMISE INSURANCE SERVICES" in broker_name.upper()
        else False
    )

    # ---------------------------------------------------
    # DATE
    # ---------------------------------------------------

    invoice_date = get_value_after_label(lines, "DATE")

    if invoice_date:
        data["invoice_date"] = normalize_date(invoice_date)

    # fallback
    if not data.get("invoice_date"):

        dates = re.findall(
            r"\b\d{2}[./-]\d{2}[./-]\d{4}\b",
            compact_text
        )

        if dates:
            data["invoice_date"] = normalize_date(dates[0])

    # ---------------------------------------------------
    # INVOICE NUMBER
    # ---------------------------------------------------

    invoice_no = get_value_after_label(lines, "INVOICE #")

    if invoice_no:

        m = re.search(r"\b\d{3}-\d{5}\b", invoice_no)

        if m:
            data["invoice_number"] = m.group()

    # fallback
    if not data.get("invoice_number"):

        m = re.search(r"\b\d{3}-\d{5}\b", compact_text)

        if m:
            data["invoice_number"] = m.group()

    # ---------------------------------------------------
    # ACCOUNT NUMBER
    # ---------------------------------------------------

    account = get_value_after_label(lines, "ACCOUNT #")

    if account:

        m = re.search(r"\b[A-Z]{3}\d{7}\b", account.upper())

        if m:
            data["account_number"] = m.group()
        else:
            data["account_number"] = account

    # ---------------------------------------------------
    # TELEPHONE
    # ---------------------------------------------------

    tel = get_value_after_label(lines, "TEL")

    if tel:

        m = re.search(r"\b\d{8,12}\b", tel)

        if m:
            data["telephone"] = m.group()

    # ---------------------------------------------------
    # VAT EMIRATE
    # ---------------------------------------------------

    emirate = get_value_after_label(lines, "EMIRATES FOR VAT")

    if emirate:
        data["emirate_for_vat"] = emirate

    # ---------------------------------------------------
    # INSURED NAME
    # ---------------------------------------------------

    for i, line in enumerate(lines):

        if line.upper() == "INSURED":

            for nxt in lines[i + 1:i + 6]:

                if (
                    re.fullmatch(r"[A-Z ]{5,}", nxt.upper())
                    and "DATE" not in nxt.upper()
                ):
                    data["insured_name"] = nxt.strip()
                    break

            break

        if line.upper().startswith("INSURED "):

            data["insured_name"] = (
                line.replace("INSURED", "", 1).strip()
            )

            break

    # fallback
    if not data.get("insured_name"):

        m = re.search(
            r"INSURED\s+(.+?)\s+PERIOD",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["insured_name"] = m.group(1).strip()

    # ---------------------------------------------------
    # POLICY + INSURANCE TYPE + PERIOD
    # ---------------------------------------------------

    for i, line in enumerate(lines):

        if re.fullmatch(POLICY_RE, line.strip()):

            data["policy_number"] = line.strip()

            # insurance type
            for candidate in reversed(lines[max(0, i - 4):i]):
            #for candidate in lines[max(0, i - 4):i]:
                candidate_upper = candidate.upper().strip()

                if (
                    "CLASS OF INSURANCE" not in candidate_upper
                    and "POLICY" not in candidate_upper
                    and not re.fullmatch(POLICY_RE, candidate.strip())
                    and len(candidate.strip()) > 3
                    ):
                    data["insurance_type"] = candidate.strip()
                    break

            # period
            nearby_text = " ".join(lines[max(0, i - 5):i + 2])

            m = re.search(
                r"(\d{2}[./-]\d{2}[./-]\d{4})\s+TO\s+(\d{2}[./-]\d{2}[./-]\d{4})",
                nearby_text,
            )

            if m:
                data["policy_start_date"] = normalize_date(m.group(1))
                data["policy_end_date"] = normalize_date(m.group(2))

            break

    # ---------------------------------------------------
    # COMMISSION EXTRACTION
    # ---------------------------------------------------

    commission_items = []

    for i, line in enumerate(lines):

        line_upper = line.upper()

        # THIRD PARTY
        if "THIRD PARTY COMMISSION" in line_upper:

            percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)

            commission_percentage = (
                percent_match.group(1)
                if percent_match
                else None
            )

            amount = None

            # amount may be next lines
            for nxt in lines[i:i + 5]:

                if is_amount(nxt):
                    amount = clean_amount(nxt)
                    break

            item = {
                "commission_type": "third_party",
                "commission_percentage": commission_percentage,
                "commission_amount": amount,
            }

            commission_items.append(item)

            data["third_party_commission_percentage"] = commission_percentage
            data["third_party_commission_amount"] = amount

        # OWN DAMAGE
        if "OWN DAMAGE COMMISSION" in line_upper:

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
                "commission_type": "own_damage",
                "commission_percentage": commission_percentage,
                "commission_amount": amount,
            }

            commission_items.append(item)

            data["own_damage_commission_percentage"] = commission_percentage
            data["own_damage_commission_amount"] = amount

    data["commission_items"] = commission_items

    # ---------------------------------------------------
    # COMMON COMMISSION %
    # ---------------------------------------------------

    percentages = []

    for item in commission_items:

        if item.get("commission_percentage"):
            percentages.append(item["commission_percentage"])

    if percentages and len(set(percentages)) == 1:
        data["commission_percentage"] = percentages[0]

    # ---------------------------------------------------
    # VAT AMOUNT
    # ---------------------------------------------------

    for i, line in enumerate(lines):

        if "5% VAT" in line.upper():

            amount = re.search(r"([\d,]+\.\d{2})$", line)

            if amount:
                data["vat_amount"] = clean_amount(amount.group(1))

            elif i + 1 < len(lines) and is_amount(lines[i + 1]):
                data["vat_amount"] = clean_amount(lines[i + 1])

            break

    # ---------------------------------------------------
    # TOTAL AMOUNT
    # ---------------------------------------------------

    for i, line in enumerate(lines):

        if line.upper().startswith("TOTAL"):

            amount = re.search(r"([\d,]+\.\d{2})$", line)

            if amount:
                data["total_amount"] = clean_amount(amount.group(1))

            elif i + 1 < len(lines) and is_amount(lines[i + 1]):
                data["total_amount"] = clean_amount(lines[i + 1])

            break

    return data