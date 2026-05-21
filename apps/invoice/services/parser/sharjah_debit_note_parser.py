import re
from datetime import datetime


def clean_amount(value):
    if not value:
        return None

    try:
        return float(str(value).replace(",", "").strip())
    except:
        return None


def clean_text(value):
    if not value:
        return None

    value = re.sub(r"[\u0600-\u06FF]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" :-")

    return value if len(value) > 1 else None


def normalize_date(value):
    if not value:
        return None

    value = str(value).strip().replace("-", "/").replace(".", "/")

    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def parse_sharjah_debit_note(text, tables=None):
    data = {}

    raw_text = text or ""
    compact_text = re.sub(r"\s+", " ", raw_text)

    data["insurer_name"] = "Sharjah Insurance"
    data["premium_currency"] = "AED"

    # Branch
    m = re.search(
        r"Branch\s*:?\s*([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )
    if m:
        value = m.group(1).split("مكتب")[0]
        data["branch"] = clean_text(value)

    # Policy type
    m = re.search(
        r"Policy\s*Type\s*:?\s*([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )
    if m:
        data["policy_type"] = clean_text(m.group(1))

    # Invoice number
    m = re.search(
        r"Tax\s*Invoice\s*No\.?\s*:?\s*(\d{4}-\d{2}-\d+)",
        raw_text,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"\b(\d{4}-\d{2}-\d+)\b",
            raw_text,
            re.IGNORECASE,
        )
    if m:
        data["invoice_number"] = m.group(1).strip()

    # Invoice date
    m = re.search(
        r"Date\s*:?\s*(\d{2}/\d{2}/\d{4})",
        raw_text,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", raw_text)
    if m:
        data["invoice_date"] = normalize_date(m.group(1))

    # Broker name
    m = re.search(
        r"Account\s*Name\s*:?\s*([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )
    if m:
        data["broker_name"] = clean_text(m.group(1))

    # Insured name
    m = re.search(
        r"Assured\s*Name\s*:?\s*([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )
    if m:
        data["insured_name"] = clean_text(m.group(1))

    # Policy number
    m = re.search(
        r"Policy\s*No\.?\s*:?\s*([A-Z0-9\/\-]+)",
        raw_text,
        re.IGNORECASE,
    )
    if m and m.group(1).strip() != "-":
        data["policy_number"] = m.group(1).strip()

    if not data.get("policy_number"):
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        for i, line in enumerate(lines):
            if "policy no" in line.lower():
                for candidate in lines[i + 1:i + 4]:
                    candidate = candidate.strip()
                    if re.match(r"^[A-Z0-9\/\-]+$", candidate) and "/" in candidate:
                        data["policy_number"] = candidate
                        break

            if data.get("policy_number"):
                break

    # Policy period
    m = re.search(
        r"(\d{2}/\d{2}/\d{4})\s*to\s*(\d{2}/\d{2}/\d{4})",
        raw_text,
        re.IGNORECASE,
    )
    if m:
        data["policy_start_date"] = normalize_date(m.group(1))
        data["policy_end_date"] = normalize_date(m.group(2))

    # Amounts
    m = re.search(
        r"TOTAL.*?([\d,]+\.\d{2})",
        raw_text,
        re.IGNORECASE | re.DOTALL,
    )

    if m:
        total = clean_amount(m.group(1))

        vat = round(total * 5 / 105, 2)
        net = round(total - vat, 2)

        data["net_premium"] = net
        data["vat_amount"] = vat

        data["total_amount"] = total
        data["total"] = total
        data["total_premium"] = total
        data["net_due"] = total

    return data



# import re
# from datetime import datetime

# POLICY_RE = r"P/\d{2}/\d{3}/\d{4}/\d{2}/\d+"


# def clean_lines(text):
#     return [line.strip() for line in text.splitlines() if line.strip()]


# def normalize_date(value):
#     if not value:
#         return None

#     value = re.sub(r"[.\-]", "/", value.strip())

#     try:
#         return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
#     except ValueError:
#         return value


# def clean_amount(value):
#     if not value:
#         return None

#     value = value.replace(",", "").strip()
#     match = re.search(r"\d+(?:\.\d{2})?", value)

#     return match.group() if match else None


# def is_amount(line):
#     return bool(re.fullmatch(r"[\d,]+\.\d{2}", line.strip()))


# def is_noise_value(value):
#     value = value.strip()

#     noise = [
#         ":",
#         ".",
#         "..",
#         "...",
#         "فاتوره ضريبيه",
#         "الفرع",
#         "نوع التأمين",
#         "رقم الأشعار",
#         "التاريخ",
#         "رقم الحساب",
#         "إسم العميل",
#     ]

#     return value in noise or value == ""


# def get_value_after_label(lines, label, lookahead=6):
#     label_lower = label.lower()

#     for i, line in enumerate(lines):
#         if label_lower in line.lower():

#             # same-line value
#             if ":" in line:
#                 value = line.split(":", 1)[1].strip()
#                 if value and not is_noise_value(value):
#                     return value

#             # next useful line
#             for nxt in lines[i + 1:i + 1 + lookahead]:
#                 cleaned = nxt.replace(":", "").strip()

#                 if not is_noise_value(cleaned):
#                     return cleaned

#     return None

# def remove_arabic(text):
#     if not text:
#         return text

#     text = re.sub(r"[\u0600-\u06FF]+", "", text)
#     text = re.sub(r"\s+", " ", text).strip()

#     return text

# def parse_sharjah_debit_note(raw_text):
#     data = {}

#     lines = clean_lines(raw_text)
#     compact_text = " ".join(lines)
#     upper_text = compact_text.upper()

#     data["document_type"] = "TAX INVOICE" if "TAX INVOICE" in upper_text else None
#     data["company_name"] = (
#         "SHARJAH INSURANCE COMPANY PSC"
#         if "SHARJAH INSURANCE" in upper_text
#         else None
#     )
#     data["is_sharjah_insurance"] = "SHARJAH INSURANCE" in upper_text

#     # Branch
#     data["branch"] = get_value_after_label(lines, "Branch")

#     # Class of insurance / policy type
#     data["policy_type"] = get_value_after_label(lines, "Policy Type")

#     # Invoice number
#     m = re.search(r"\b\d{4}-\d{2}-\d{4}\b", compact_text)
#     if m:
#         data["invoice_number"] = m.group()

#     # Invoice date
#     date_value = get_value_after_label(lines, "Date")
#     if date_value:
#         m = re.search(r"\d{2}[./-]\d{2}[./-]\d{4}", date_value)
#         if m:
#             data["invoice_date"] = normalize_date(m.group())

#     if not data.get("invoice_date"):
#         m = re.search(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", compact_text)
#         if m:
#             data["invoice_date"] = normalize_date(m.group())

#     # Account number
#     data["account_number"] = get_value_after_label(lines, "Account Code")

#     # Broker name

#     broker_name = get_value_after_label(lines, "Account Name")

#     if broker_name:
#         cleaned_broker = remove_arabic(broker_name).upper()
#         # Standardize Promise broker
#         if "PROMISE INSURANCE" in cleaned_broker:
#             data["broker_name"] = "PROMISE INSURANCE SERVICES"
#         else:
#             data["broker_name"] = remove_arabic(broker_name)

#     # Promise broker validation
#     broker_name = data.get("broker_name", "")

#     data["is_promise_broker"] = (
#         "PROMISE INSURANCE" in broker_name.upper()
#         )
    
#     # Tax registration number / VAT no
#     vat = get_value_after_label(lines, "VAT No")
#     if vat:
#         m = re.search(r"\b\d{15}\b", vat)
#         if m:
#             data["tax_registration_number"] = m.group()

#     if not data.get("tax_registration_number"):
#         m = re.search(r"\b\d{15}\b", compact_text)
#         if m:
#             data["tax_registration_number"] = m.group()

#     # Insured name
#     data["insured_name"] = get_value_after_label(lines, "Assured Name")

#     # Policy number
#     m = re.search(POLICY_RE, compact_text)
#     if m:
#         data["policy_number"] = m.group()

#     # Premium amount
#     for i, line in enumerate(lines):
#         if "Being Premium" in line:
#             for nxt in lines[i:i + 5]:
#                 m = re.search(r"[\d,]+\.\d{2}", nxt)
#                 if m:
#                     data["premium_amount"] = clean_amount(m.group())
#                     break

#     # VAT amount
#     for i, line in enumerate(lines):
#         if "VAT" in line.upper() and "5%" in line:
#             for nxt in lines[i:i + 5]:
#                 m = re.search(r"[\d,]+\.\d{2}", nxt)
#                 if m:
#                     data["vat_amount"] = clean_amount(m.group())
#                     break

#     # Vehicle details
#     for i, line in enumerate(lines):
#         if line.strip().lower() == "vehicle":
#             nearby = lines[i + 1:i + 5]
#             vehicle_parts = []
#             for part in nearby:
#                 cleaned = part.replace(":", "").strip()

#                 # skip arabic/noise
#                 if not cleaned:
#                     continue
#                 if re.search(r"[\u0600-\u06FF]", cleaned):
#                     continue

#                 if cleaned.lower() in ["model", "regn.no.", "chassis.no."]:
#                     break

#                 vehicle_parts.append(cleaned)

#                 if vehicle_parts:
#                     data["vehicle_make"] = " ".join(vehicle_parts)
#                     break

#     model = get_value_after_label(lines, "Model")
#     if model:
#         data["vehicle_model_year"] = model

#     reg_no = get_value_after_label(lines, "Regn.No")
#     if reg_no:
#         data["vehicle_reg_no"] = reg_no

#     chassis = get_value_after_label(lines, "Chassis.No")
#     if chassis:
#         data["chassis_number"] = chassis

#     # Period of insurance
#     period = get_value_after_label(lines, "Period of Ins")
#     if period:
#         m = re.search(
#             r"(\d{2}[./-]\d{2}[./-]\d{4})\s+to\s+(\d{2}[./-]\d{2}[./-]\d{4})",
#             period,
#             re.IGNORECASE,
#         )
#         if m:
#             data["period_from"] = normalize_date(m.group(1))
#             data["period_to"] = normalize_date(m.group(2))

#     if not data.get("period_from"):
#         m = re.search(
#             r"(\d{2}[./-]\d{2}[./-]\d{4})\s+to\s+(\d{2}[./-]\d{2}[./-]\d{4})",
#             compact_text,
#             re.IGNORECASE,
#         )
#         if m:
#             data["period_from"] = normalize_date(m.group(1))
#             data["period_to"] = normalize_date(m.group(2))

#     # Total amount
#     for i, line in enumerate(lines):
#         if line.upper().startswith("TOTAL"):
#             for nxt in lines[i:i + 6]:
#                 m = re.search(r"[\d,]+\.\d{2}", nxt)
#                 if m:
#                     data["total_amount"] = clean_amount(m.group())
#                     break

#     return data