import re
from datetime import datetime

POLICY_RE = r"\d{2}/\d{4}/\d{2}[A-Z]/\d+"

def clean_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_date(value):
    if not value:
        return None

    value = re.sub(r"[.\-]", "/", value)

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
            if ":" in line:
                value = line.split(":", 1)[1].strip()
                if value:
                    return value

            # next useful line
            for nxt in lines[i + 1:i + 1 + lookahead]:
                cleaned = nxt.replace(":", "").strip()
                if cleaned:
                    return cleaned

    return None

def is_amount(line):
    return bool(re.fullmatch(r"[\d,]+\.\d{2}", line.strip()))


def parse_fidelity_debit_note(text,tables=None):

    data = {}
    lines = clean_lines(text)
    compact_text = " ".join(lines)
    upper_text = compact_text.upper()


    # Basic fields
    data["document_type"] = "TAX INVOICE" if "TAX INVOICE" in compact_text else None
    data["company_name"] = (
        "UNITED FIDELITY INSURANCE COMPANY"
        if "UNITED FIDELITY INSURANCE COMPANY" in compact_text
        else None
    )
    data["is_fidelity"] = (
        "FIDELITY" in compact_text.upper()
        or "UNITED FIDELITY INSURANCE COMPANY" in compact_text.upper()
        )
    
    data["premium_currency"] = "AED"

    # Branch 
    for line in lines:
        line = line.strip()

        if line.upper().startswith("BRANCH"):

            branch = re.sub(
                r"^BRANCH\s*:?\s*",
                "",
                line,
                flags=re.IGNORECASE
            ).strip()

            if branch:
                data["branch"] = branch
                break

    # for i, line in enumerate(lines):
    #     if line.strip().upper() == "BRANCH":
    #         if i + 1 < len(lines):
    #             data["branch"] = lines[i + 1].strip()
    #         break

    # # Fallback for same-line branch format
    # if not data.get("branch"):
    #     m = re.search(
    #         r"BRANCH\s+([A-Z ]+?)(?:\s+[A-Z ]+\s+EMIRATES\s+FOR\s+VAT|\s+DATE|\s+TEL|\s+TAX\s+REGN|\s+ACCOUNT|\s+INSURED)",
    #         compact_text,
    #         re.IGNORECASE,
    #     )

    #     if m:
    #         data["branch"] = re.sub(r"\s+", " ", m.group(1)).strip()

    # Dates
    invoice_date = get_value_after_label(lines, "DATE")
    if invoice_date:
        data["invoice_date"] = normalize_date(invoice_date)


    # Invoice number
    invoice_no = get_value_after_label(lines, "INVOICE #")
    if invoice_no:
        m = re.search(r"([A-Z0-9][A-Z0-9/\-]{3,})", invoice_no.upper())
        if m:
            data["invoice_number"] = m.group(1).strip()

    if not data.get("invoice_number"):
            m = re.search(
                r"(?:Tax\s*Invoice|Invoice)\s*(?:#|No\.?|Number)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-]{3,})",
                compact_text,
                re.IGNORECASE,
            )
            if m:
                data["invoice_number"] = m.group(1).strip()


    # Tax registration number
    m = re.search(r"\b\d{15}\b", compact_text)
    if m:
        data["tax_registration_number"] = m.group()

    # Account number
    data["account_number"] = get_value_after_label(lines, "ACCOUNT #")

    # Emirates for VAT
    data["emirate_for_vat"] = get_value_after_label(lines, "EMIRATES FOR VAT")
    

    # Broker name
    for i, line in enumerate(lines):
        upper_line = line.upper().strip()

        if (
            "PROMISE INSURANCE" in upper_line
            or "PROMISE INSURANCE SERVICES" in upper_line
            ):
            data["broker_name"] = line.strip()
            break

    # Fallback
    if not data.get("broker_name"):
        m = re.search(
            r"(PROMISE INSURANCE SERVICES(?: LLC)?)",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["broker_name"] = m.group(1).strip()

    # Promise broker validation
    broker_name = data.get("broker_name", "")

    data["is_promise_broker"] = (
        "PROMISE INSURANCE" in broker_name.upper()
        )
    
    # Insured name
    for i, line in enumerate(lines):
        if line.strip().upper() == "INSURED":
            for nxt in lines[i + 1:i + 5]:
                candidate = nxt.strip()

                if re.search(
                    r"^(CLASS\s+OF\s+INSURANCE|POLICY|PERIOD|VEHICLE|DATE|INVOICE|TAX)",
                    candidate,
                    re.IGNORECASE,
                ):
                    break

                if len(candidate) > 3:
                    data["insured_name"] = candidate
                    break

            break

    if not data.get("insured_name"):
        m = re.search(
            r"INSURED\s+(.+?)\s+CLASS\s+OF\s+INSURANCE",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            data["insured_name"] = re.sub(r"\s+", " ", m.group(1)).strip()


 # Policy period
    m = re.search(
        r"PERIOD\s+(\d{2}[./-]\d{2}[./-]\d{4})\s+TO\s+(\d{2}[./-]\d{2}[./-]\d{4})",
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["policy_start_date"] = normalize_date(m.group(1))
        data["policy_end_date"] = normalize_date(m.group(2))

    # Policy number
    m = re.search(POLICY_RE, compact_text)
    if m:
        data["policy_number"] = m.group()

    # Policy type
    m = re.search(
        r"CLASS\s+OF\s+INSURANCE\s+POLICY\s*#\s+(.+?)\s+" + POLICY_RE,
        compact_text,
        re.IGNORECASE,
    )
    if m:
        data["policy_type"] = re.sub(r"\s+", " ", m.group(1)).strip()

    if not data.get("policy_type") and data.get("policy_number"):
        idx = compact_text.find(data["policy_number"])
        before = compact_text[:idx]
        m = re.search(r"(MOTOR\s+[A-Z .]+)$", before, re.IGNORECASE)
        if m:
            data["policy_type"] = re.sub(r"\s+", " ", m.group(1)).strip()

    # Premium amount
    for i, line in enumerate(lines):
        if "Payment Ref No" in line:
            for nxt in lines[i + 1:i + 5]:
                if is_amount(nxt):
                    data["net_premium"] = clean_amount(nxt)
                    break

    # VAT
    for i, line in enumerate(lines):
        if "5% VAT" in line:
            m = re.search(r"([\d,]+\.\d{2})$", line)
            if m:
                data["vat_amount"] = clean_amount(m.group(1))
            elif i + 1 < len(lines) and is_amount(lines[i + 1]):
                data["vat_amount"] = clean_amount(lines[i + 1])

    # Total
    for i, line in enumerate(lines):
        if line.startswith("TOTAL"):
            m = re.search(r"([\d,]+\.\d{2})$", line)
            if m:
                total = clean_amount(m.group(1))
            else:
                total = None
                for nxt in lines[i + 1:i + 5]:
                    if is_amount(nxt):
                        total = clean_amount(nxt)
                        break

            if total is not None:
                data["total_amount"] = total
                data["total"] = total
                data["total_premium"] = total
                data["net_due"] = total

    # Summary fallback
    for i, line in enumerate(lines):
        if line == "PREMIUM AMOUNT" and i + 1 < len(lines):
            data["net_premium"] = clean_amount(lines[i + 1])

        if line == "VAT AMOUNT" and i + 1 < len(lines):
            data["vat_amount"] = clean_amount(lines[i + 1])

    if not data.get("total_amount") and data.get("net_premium") and data.get("vat_amount"):
        total = round(data["net_premium"] + data["vat_amount"], 2)
        data["total_amount"] = total
        data["total"] = total
        data["total_premium"] = total
        data["net_due"] = total


    unwanted_fields = [
        "is_fidelity",
        "account_number",
        "telephone",
        "emirate_for_vat",
        "is_promise_broker",
    ]

    for field in unwanted_fields:
        data.pop(field, None)

    return data

