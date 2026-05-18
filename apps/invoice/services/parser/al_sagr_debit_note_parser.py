import re


def clean_amount(value):
    if not value:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except:
        return None


def parse_al_sagr_debit_note(text, tables=None):
    data = {}

    data["insurer_name"] = "Al Sagr National Insurance"

    # Invoice / debit note number
    m = re.search(
        r"(?:Invoice\s*Number|Tax\s*Invoice\s*No\.?|Invoice\s*No\.?)\s*[\n: ]+\s*([A-Z0-9\-\/]+)",
        text,
        re.IGNORECASE
    )
    data["invoice_number"] = m.group(1).strip() if m else None

    # Invoice date
    m = re.search(
        r"(?:Invoice\s*Date|Date)\s*[\n: ]+\s*(\d{2}/\d{2}/\d{4})",
        text,
        re.IGNORECASE
    )
    data["invoice_date"] = m.group(1).strip() if m else None

    # Customer / insured name
    m = re.search(
        r"(?:Insured\s*Name|Customer\s*Name|Insured)\s*[\n: ]+\s*(.+)",
        text,
        re.IGNORECASE
    )
    data["insured_name"] = re.sub(r"\s+", " ", m.group(1).strip()) if m else None

    # Broker name
    m = re.search(
        r"(?:Broker\s*Name|Broker|Agent)\s*[\n: ]+\s*(.+)",
        text,
        re.IGNORECASE
    )
    broker_name = re.sub(r"\s+", " ", m.group(1).strip()) if m else None
    data["broker_name"] = broker_name
    data["is_promise_broker"] = "PROMISE INSURANCE" in (broker_name or "").upper()

    # Policy number
    m = re.search(
        r"(?:Policy\s*No\.?|Policy\s*Number)\s*[\n: ]+\s*([A-Z0-9\/\-]+)",
        text,
        re.IGNORECASE
    )
    data["policy_number"] = m.group(1).strip() if m else None

    # Policy type
    m = re.search(
        r"(?:Policy\s*Type|Insurance\s*Type)\s*[\n: ]+\s*(.+)",
        text,
        re.IGNORECASE
    )
    data["policy_type"] = re.sub(r"\s+", " ", m.group(1).strip()) if m else None

    # Policy period
    compact_text = re.sub(r"\s+", " ", text)

    m = re.search(
        r"(?:Period\s*of\s*Ins\.?|Period\s*of\s*Insurance|Extended\s*Period)\s*[: ]*"
        r"(\d{2}/\d{2}/\d{4})\s*to\s*(\d{2}/\d{2}/\d{4})",
        compact_text,
        re.IGNORECASE
    )

    if m:
        data["policy_start_date"] = m.group(1)
        data["policy_end_date"] = m.group(2)
    else:
        dates = re.findall(r"\d{2}/\d{2}/\d{4}", compact_text)
        data["policy_start_date"] = dates[0] if len(dates) >= 1 else None
        data["policy_end_date"] = dates[1] if len(dates) >= 2 else None

    data["premium_currency"] = "AED"

    # Amounts
    total = None
    net_premium = None
    vat_amount = None

    m = re.search(
        r"Total\s*Amount.*?([\d,]+\.\d{2})",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if m:
        total = clean_amount(m.group(1))
        if total:
            vat_amount = round(total * 5 / 105, 2)
            net_premium = round(total - vat_amount, 2)

    if not total:
        m = re.search(r"5%\s*[\n ]+([\d,]+\.\d+)", text, re.IGNORECASE)
        if m:
            net_premium = clean_amount(m.group(1))
            if net_premium:
                vat_amount = round(net_premium * 0.05, 2)
                total = round(net_premium + vat_amount, 2)

    data["net_premium"] = net_premium
    data["vat_amount"] = vat_amount
    data["total"] = total
    data["total_premium"] = total
    data["net_due"] = total

    return data



# import re
# from datetime import datetime

# POLICY_RE = r"P/[A-Z]{2}/\d{4}/\d{2}/\d+"


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
#         "",
#         ":",
#         ".",
#         "..",
#         "رقــــم",
#         "الفاتـــــــورة",
#         "تاريــخ الفاتـــورة",
#         "Date Invoice",
#         "الفاتـــورة عمـــــله",
#         "سعـــــــر الصـــرف",
#         "التأميـــــــن مــــــدة",
#         "له المؤمــن ســم أ",
#         "التأميـــن نـــــــــوع",
#     ]

#     return value in noise

# def remove_arabic(text):
#     if not text:
#         return text

#     text = re.sub(r'[\u0600-\u06FF]+', '', text)

#     text = re.sub(r'\s+', ' ', text).strip()

#     return text


# def get_value_after_label(lines, label, lookahead=6):
#     label_lower = label.lower()

#     for i, line in enumerate(lines):
#         if label_lower in line.lower():

#             # Same line value
#             if ":" in line:
#                 value = line.split(":", 1)[1].strip()
#                 if value and not is_noise_value(value):
#                     return value

#             # Next useful line
#             for nxt in lines[i + 1:i + 1 + lookahead]:
#                 cleaned = nxt.replace(":", "").strip()

#                 if not is_noise_value(cleaned):
#                     return cleaned

#     return None


# def parse_al_sagr_debit_note(raw_text):
#     data = {}

#     lines = clean_lines(raw_text)
#     compact_text = " ".join(lines)
#     upper_text = compact_text.upper()

#     # Basic fields
#     data["document_type"] = "TAX INVOICE" if "TAX INVOICE" in upper_text else None
#     data["company_name"] = (
#         "AL SAGR NATIONAL INSURANCE CO.(PSC)"
#         if "AL SAGR" in upper_text or "ASNIC" in upper_text
#         else None
#     )
#     data["is_al_sagr"] = "AL SAGR" in upper_text or "ASNIC" in upper_text

#     # Tax registration number
#     m = re.search(r"ASNIC\s+TRN\s*#?\s*(\d{15})", compact_text, re.IGNORECASE)
#     if m:
#         data["tax_registration_number"] = m.group(1)
#     else:
#         m = re.search(r"\b\d{15}\b", compact_text)
#         if m:
#             data["tax_registration_number"] = m.group()

#     # Customer TRN if needed
#     trns = re.findall(r"\b\d{15}\b", compact_text)
#     if len(trns) > 1:
#         data["customer_tax_registration_number"] = trns[1]

#     # Invoice number
#     m = re.search(r"Invoice Number\s+([A-Z0-9\-]+)", compact_text, re.IGNORECASE)
#     if m:
#         data["invoice_number"] = m.group(1)

#     if not data.get("invoice_number"):
#         m = re.search(r"\b\d{3}-\d{8}\b", compact_text)
#         if m:
#             data["invoice_number"] = m.group()

#     # Invoice date
#     m = re.search(
#         r"(\d{2}[./-]\d{2}[./-]\d{4})\s+Date Invoice",
#         compact_text,
#         re.IGNORECASE,
#     )
#     if m:
#         data["invoice_date"] = normalize_date(m.group(1))

#     if not data.get("invoice_date"):
#         date_value = get_value_after_label(lines, "Invoice Date")
#         if date_value:
#             m = re.search(r"\d{2}[./-]\d{2}[./-]\d{4}", date_value)
#             if m:
#                 data["invoice_date"] = normalize_date(m.group())

#     # Policy number
#     m = re.search(POLICY_RE, compact_text)
#     if m:
#         data["policy_number"] = m.group()

#     # Policy period
#     m = re.search(
#         r"Period of Ins\.?\s+(\d{2}[./-]\d{2}[./-]\d{4})\s+to\s+(\d{2}[./-]\d{2}[./-]\d{4})",
#         compact_text,
#         re.IGNORECASE,
#     )
#     if m:
#         data["period_from"] = normalize_date(m.group(1))
#         data["period_to"] = normalize_date(m.group(2))

#     # Insured name
#     m = re.search(
#         r"Insured Name\s+(.+?)\s+Policy Type",
#         compact_text,
#         re.IGNORECASE,
#     )
#     if m:
#         data["insured_name"] = remove_arabic(m.group(1).strip())

#     # Class of insurance / policy type
#     m = re.search(
#         r"Policy Type\s+(.+?)\s+Branch",
#         compact_text,
#         re.IGNORECASE,
#     )
#     if m:
#         data["class_of_insurance"] = remove_arabic(m.group(1).strip())

#     # Branch
#     branch = get_value_after_label(lines, "Branch")
#     if branch:
#         data["branch"] = remove_arabic(branch)

#     # Account number
#     m = re.search(r"(\d{8})\s+Code Account", compact_text, re.IGNORECASE)
#     if m:
#         data["account_number"] = m.group(1)

#     if not data.get("account_number"):
#         account_number = get_value_after_label(lines, "Account Code")
#         if account_number:
#             data["account_number"] = account_number

#     # Account name
#     m = re.search(
#         r"Account\s+Name\s+(.+?)\s+رمز الوسيط",
#         compact_text,
#         re.IGNORECASE,
#     )
#     if m:
#         data["account_name"] = m.group(1).strip()

#     if not data.get("account_name"):
#         account_name = get_value_after_label(lines, "Account Name")
#         if account_name:
#             data["account_name"] = account_name

#     # Broker name
#     m = re.search(
#         r"Broker Name\s+(.+?)\s+Please note",
#         compact_text,
#         re.IGNORECASE,
#         )

#     if m:
#         broker_name = remove_arabic(m.group(1).strip())
#         data["broker_name"] = broker_name

#     if not data.get("broker_name"):
#         broker_name = get_value_after_label(lines, "Broker Name")

#         if broker_name:
#             data["broker_name"] = remove_arabic(broker_name)

#     # Check if broker is Promise Insurance
#     broker_name = data.get("broker_name", "")

#     data["is_promise_broker"] = (
#         "PROMISE INSURANCE" in broker_name.upper()
#         )

#     # Premium amount
#     m = re.search(
#         r"Being Premium.*?(\d[\d,]*\.\d{2})\s+(\d[\d,]*\.\d{2})",
#         compact_text,
#         re.IGNORECASE,
#     )
#     if m:
#         data["premium_amount"] = clean_amount(m.group(1))

#     if not data.get("premium_amount"):
#         m = re.search(r"SubTotal\s+([\d,]+\.\d{2})", compact_text, re.IGNORECASE)
#         if m:
#             data["premium_amount"] = clean_amount(m.group(1))

#     # VAT amount
#     m = re.search(r"VAT@5%\s+([\d,]+\.\d{2})", compact_text, re.IGNORECASE)
#     if m:
#         data["vat_amount"] = clean_amount(m.group(1))

#     # Total amount
#     m = re.search(r"Invoice Total\s+([\d,]+\.\d{2})", compact_text, re.IGNORECASE)
#     if m:
#         data["total_amount"] = clean_amount(m.group(1))

#     # Vehicle make
#     vehicle = get_value_after_label(lines, "Vehicle")
#     if vehicle:
#         data["vehicle_make"] = vehicle

#     # Model
#     model = get_value_after_label(lines, "Model")
#     if model:
#         data["vehicle_model_year"] = model

#     # Registration number
#     regn = get_value_after_label(lines, "Regn.No")
#     if regn:
#         data["vehicle_reg_no"] = regn

#     # Chassis number can be on page 2
#     m = re.search(r"Chassis\.?No\s*:\s*([A-Z0-9]+)", compact_text, re.IGNORECASE)
#     if m:
#         data["chassis_number"] = m.group(1)

#     if not data.get("chassis_number"):
#         for i, line in enumerate(lines):
#             if "chassis" in line.lower():
#                 nearby = " ".join(lines[i:i + 3])
#                 m = re.search(r"\b[A-Z0-9]{10,25}\b", nearby)
#                 if m:
#                     data["chassis_number"] = m.group()
#                     break

#     return data