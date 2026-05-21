import re
from .utils import clean_lines, normalize_date, clean_amount


POLICY_RE = r"AU\d+"


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

def parse_watania_credit_note(raw_text):

    data = {}

    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
    upper_text = compact_text.upper()

    # Use buyer-created credit note section if present
    buyer_marker = "Tax Credit Note Created By Buyer"

    raw_upper = raw_text.upper()

    if buyer_marker.upper() in raw_upper:
        start = raw_upper.find(buyer_marker.upper())
        raw_text = raw_text[start:]
    
    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
    upper_text = compact_text.upper()

    # Basic fields
    data["document_type"] = (
        "CREDIT NOTE"
        
        if("CREDIT NOTE" in upper_text
           or "TAX CREDIT NOTE" in upper_text
           or "TAX INVOICE RAISED BY BUYER" in upper_text
        )
        else None
    )

    data["company_name"] = (
        "WATANIA TAKAFUL GENERAL P.J.S.C."
        if "WATANIA" in upper_text
        else None
    )

    data["is_watania"] = "WATANIA" in upper_text

    # Branch
    branch = get_next_value(lines, "Branch")
    if branch:
        data["branch"] = branch

    if not data.get("branch"):
        m = re.search(r"\bWTG-[A-Za-z]+\b", compact_text)
        if m:
            data["branch"] = m.group()

    # Invoice date
    invoice_date = get_next_value(lines, "Invoice Date")
    if invoice_date:
        m = re.search(r"\d{2}[./-]\d{2}[./-]\d{4}", invoice_date)
        if m:
            data["invoice_date"] = normalize_date(m.group())

    if not data.get("invoice_date"):
        dates = re.findall(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", compact_text)
        if dates:
            data["invoice_date"] = normalize_date(dates[0])

    # Invoice number / Document No
    m = re.search(
        r"Document No\.?\s*:?\s*((?:CN|DN)-[A-Z]+-\d{2}-\d{2}-\d+)",
        #r"Document No\.?\s*:?\s*(CN-[A-Z]+-\d{2}-\d{2}-\d+)",
        compact_text,
        re.IGNORECASE
    )
    if m:
        data["invoice_number"] = m.group(1)

    # Original invoice number
    m = re.search(
        r"Original Tax Invoice No\.?\s*:?\s*((?:CN|DN)-[A-Z]+-\d{2}-\d{2}-\d+)",
        #r"Original Tax Invoice No\.?\s*:?\s*(CN-[A-Z]+-\d{2}-\d{2}-\d+)",
        compact_text,
        re.IGNORECASE
    )
    if m:
        data["original_invoice_number"] = m.group(1)


    # Insured / Client name
    client_name = get_next_value(lines, "Client Name")
    if client_name:
        data["insured_name"] = client_name

    # Broker name
    broker_name = get_next_value(lines, "Broker Name")
    if broker_name:
        broker_name = broker_name.replace("LLC(WTG)", "")
        broker_name = broker_name.replace("L.L.C.", "")
        broker_name = broker_name.replace("LLC", "")
        broker_name = broker_name.strip()
        data["broker_name"] = broker_name

    data["is_promise_broker"] = (
        "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
    )

    # Broker TRN
    broker_trn = get_next_value(lines, "Broker TRN")
    if broker_trn:
        m = re.search(r"\d{15}", broker_trn)
        if m:
            data["broker_tax_registration_number"] = m.group()

    # Company TRN
    m = re.search(r"Watania Takaful General.*?TRN\s*:?\s*(\d{15})", compact_text, re.IGNORECASE)
    if m:
        data["tax_registration_number"] = m.group(1)

    # Policy number / Takaful certificate
    m = re.search(
        r"\bAU\d+(?:/[A-Z0-9]+)?\b",
        # r"Takaful Certificate\s+(AU\d+)", 
        compact_text, 
        re.IGNORECASE
        )
    if m:
        data["policy_number"] = m.group()

    if not data.get("policy_number"):
        m = re.search(r"\bAU\d+\b", compact_text)
        if m:
            data["policy_number"] = m.group()
     
    #Policy start and end date 
    m = re.search(
        r"for the period of\s*(\d{2}/\d{2}/\d{4})\s*to\s*(\d{2}/\d{2}/\d{4})",
        compact_text,
        re.IGNORECASE
    )
    if m:
        data["policy_start_date"] = normalize_date(m.group(1))
        data["policy_end_date"] = normalize_date(m.group(2))

    # Policy type
    policy_type = get_next_value(lines, "Takaful Certificate Type")
    if policy_type:
        data["policy_type"] = policy_type

    # Commission amount
    commission = get_next_value(lines, "Total Commission")
    if commission:
        m = re.search(r"[\d,]+\.\d{2}", commission)
        if m:
            data["commission_amount"] = clean_amount(m.group())

    commission_due = get_next_value(lines, "Commission Amount Due")
    if commission_due:
        m = re.search(r"[\d,]+\.\d{2}", commission_due)
        if m:
            data["commission_amount_due"] = clean_amount(m.group())

    data["commission_items"] = []

    if data.get("commission_amount"):
        data["commission_items"].append({
            "commission_type": "agent_commission",
            "commission_percentage": None,
            "commission_amount": data["commission_amount"],
        })

    # VAT
    vat = get_next_value(lines, "VAT 5%")
    if vat:
        m = re.search(r"[\d,]+\.\d{2}", vat)
        if m:
            data["vat_amount"] = clean_amount(m.group())
    
    if not data.get("vat_amount"):
        m = re.search(r"VAT\s*5%\s*[:.]?\s*([\d,]+\.\d{2})\s*AED", compact_text, re.IGNORECASE)
        if m:
            data["vat_amount"] = clean_amount(m.group(1))

    # Total amount - only search above installments table
    amount_section = re.split(
        r"No\.?\s*Of\s*Installments|Grand Total|Dear Valued Customers",
        compact_text,
        flags=re.IGNORECASE
    )[0]

    # prefer Total Amount Payable
    m = re.search(
        r"Total Amount Payable\s*:?\s*([\d,]+\.\d{2})\s*AED",
        amount_section,
        re.IGNORECASE
    )
    if m:
        data["total_amount"] = clean_amount(m.group(1))

    # fallback: plain Total
    if not data.get("total_amount"):
        m = re.search(
            r"\bTotal\s*:?\s*([\d,]+\.\d{2})\s*AED",
            amount_section,
            re.IGNORECASE
        )
        if m:
            data["total_amount"] = clean_amount(m.group(1))

    return data