import re
from datetime import datetime


def normalize_date(value):
    if not value:
        return None

    value = value.strip().replace("/", "-")

    for fmt in (
        "%d-%m-%Y",
        "%d-%m-%y",
        "%m-%d-%Y",
        "%m-%d-%y",
        "%d-%b-%Y",
        "%d-%B-%Y",
    ):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


# def normalize_date(value):
#     if not value:
#         return None

#     value = value.strip().replace("-", "/")

#     for fmt in ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%m/%d/%y"):
#         try:
#             return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
#         except ValueError:
#             continue

#     return value


def clean_amount(value):
    if not value:
        return None

    try:
        value = str(value)
        value = value.replace(",", "")
        value = value.replace("(", "-").replace(")", "")
        return float(value.strip())
    except:
        return None
    
def extract_policy_date_range(text):
    compact = re.sub(r"\s+", " ", text)

    patterns = [
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",

        r"FROM\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}).*?TO\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",

        r"(\d{1,2}-[A-Za-z]{3}-\d{4})\s+\d{1,2}:\d{2}\s*To\s*(\d{1,2}-[A-Za-z]{3}-\d{4})\s+\d{1,2}:\d{2}",
    ]

    for pattern in patterns:
        m = re.search(pattern, compact, re.IGNORECASE)
        if m:
            return normalize_date(m.group(1)), normalize_date(m.group(2))

    return None, None


# def extract_policy_date_range(text):
#     compact = re.sub(r"\s+", " ", text)

#     patterns = [
#         r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
#         r"FROM\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}).*?TO\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
#     ]

#     for pattern in patterns:
#         m = re.search(pattern, compact, re.IGNORECASE)
#         if m:
#             return normalize_date(m.group(1)), normalize_date(m.group(2))

#     return None, None


def get_table_rows(tables):
    rows = []

    if not tables:
        return rows

    for table in tables:
        # Your Azure table format is usually: {0: {0: "A", 1: "B"}}
        if isinstance(table, dict):
            for row_idx in sorted(table.keys()):
                row_dict = table[row_idx]
                if isinstance(row_dict, dict):
                    row = [row_dict[col] for col in sorted(row_dict.keys())]
                    rows.append(row)

        # Her format: {"grid": [[...], [...]]}
        elif isinstance(table, dict) and "grid" in table:
            rows.extend(table.get("grid", []))

    return rows


def extract_numbers_from_row(row):
    nums = []

    for cell in row:
        value = clean_amount(cell)
        if value is not None:
            nums.append(value)

    return nums


def extract_table_amounts(tables):
    result = {
        "net_premium": None,
        "vat_amount": None,
        "total_amount": None,
    }

    rows = get_table_rows(tables)

    best_row = None

    for row in rows:
        row_text = " ".join(str(x) for x in row).lower()

        if any(x in row_text for x in [
            "grand total",
            "total due",
            "invoice total",
            "total"
        ]):
            best_row = row

    if not best_row:
        return result

    numbers = extract_numbers_from_row(best_row)

    if len(numbers) >= 2:
        total = abs(numbers[-1])
        vat = abs(numbers[-2])
        net = round(total - vat, 2)

        result["net_premium"] = net
        result["vat_amount"] = vat
        result["total_amount"] = total

    return result


def parse_qic_debit_note(text, tables=None):
    data = {}

    text_upper = text.upper()

    data["insurer_name"] = "QIC"
    data["premium_currency"] = "AED"

    # Customer / insured name
    patterns = [
        r"Insured\s*:?\s*([^\n\r]+)",
        r"Customer\s*Name\s*:?\s*([^\n\r]+)",
        r"Insured\s*Name\s*:?\s*([^\n\r]+)",
        r"Policy\s*Holder\s*:?\s*([^\n\r]+)",
    ]

    data["insured_name"] = None
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            value = re.split(
                r"(Policy|Broker|Invoice|Date|TRN)",
                value,
                maxsplit=1,
                flags=re.IGNORECASE
            )[0].strip()

            if len(value) > 2:
                data["insured_name"] = value
                break

    # Broker name
    patterns = [
        r"Broker\s*:?\s*([^\n\r]+)",
        r"Broker\s*Name\s*:?\s*([^\n\r]+)",
        r"Intermediary\s*:?\s*([^\n\r]+)",
        r"Agent\s*:?\s*([^\n\r]+)",
    ]

    broker_name = None
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            value = re.split(
                r"(Policy|Invoice|Date|TRN)",
                value,
                maxsplit=1,
                flags=re.IGNORECASE
            )[0].strip()

            if len(value) > 2:
                broker_name = value
                break

    data["broker_name"] = broker_name
    data["is_promise_broker"] = "PROMISE INSURANCE" in (broker_name or "").upper()

    # Invoice date
    compact = re.sub(r"\s+", " ", text)
    m = re.search(
        r"(?:Invoice\s*Date|Date)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        compact,
        re.IGNORECASE
    )
    data["invoice_date"] = normalize_date(m.group(1)) if m else None

    # Branch
    m = re.search(r"Branch\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
    data["branch"] = m.group(1).strip() if m else None

    # Policy type
    m = re.search(r"Product\s*:\s*(.+)", text, re.IGNORECASE)
    data["policy_type"] = m.group(1).strip() if m else None

    # Policy number
    data["policy_number"] = None
    patterns = [
        r"Policy\s*No\.?\s*:?\s*([A-Za-z0-9\s\-\/]+)",
        r"Policy\s*Number\s*:?\s*([A-Za-z0-9\s\-\/]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = m.group(1).replace(" ", "").strip()
            value = re.split(
                r"POLICY|PERIOD|FROM|TO|DATE",
                value,
                maxsplit=1,
                flags=re.IGNORECASE
            )[0].strip()
            value = re.sub(r"[^A-Z0-9/\-]", "", value.upper())

            if len(value) >= 5:
                data["policy_number"] = value
                break

    # Invoice number
    data["invoice_number"] = None
    patterns = [
        r"Doc\s*No\.?\s*:?\s*([A-Z0-9\s\-\/]+)",
        r"(?:Tax\s*Invoice|Invoice)\s*(?:No\.?|Number)\s*:?\s*([A-Z0-9\s\-\/]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = m.group(1).replace(" ", "").strip()
            value = re.split(
                r"DATE|POLICY|PERIOD|FROM|TO",
                value,
                maxsplit=1,
                flags=re.IGNORECASE
            )[0].strip()
            value = re.sub(r"[^A-Z0-9/\-]", "", value.upper())

            if len(value) >= 4:
                data["invoice_number"] = value
                break

    # Policy period
    policy_start_date, policy_end_date = extract_policy_date_range(text)

    data["policy_start_date"] = policy_start_date
    data["policy_end_date"] = policy_end_date

    # Amounts from tables
    amounts = extract_table_amounts(tables)

    data.update(amounts)


    # Fallback: read QIC TOTAL row directly
    if not data.get("total_amount"):
        compact = re.sub(r"\s+", " ", text)

        total_match = re.search(
            r"TOTAL\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
            compact,
            re.IGNORECASE
            )

        if total_match:
            net = clean_amount(total_match.group(2))
            vat = clean_amount(total_match.group(3))
            total = clean_amount(total_match.group(4))

            data["net_premium"] = net
            data["vat_amount"] = vat
            data["total_amount"] = total

    # # Fallback: if table fails, pull all amounts and use last two
    # if not data.get("total"):
    #     all_amounts = re.findall(r"\(?[\d,]+\.\d{2}\)?", text)
    #     cleaned = [clean_amount(x) for x in all_amounts]
    #     cleaned = [x for x in cleaned if x is not None]

    #     if len(cleaned) >= 2:
    #         total = abs(cleaned[-1])
    #         vat = abs(cleaned[-2])
    #         net = round(total - vat, 2)

    #         data["premium_amount"] = total
    #         data["net_premium"] = net
    #         data["total_premium"] = total
    #         data["vat_amount"] = vat
    #         data["net_due"] = total
    #         data["total"] = total

    return data