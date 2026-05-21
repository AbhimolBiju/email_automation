import re
from datetime import datetime


def clean_amount(value):
    if not value:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except:
        return None


def normalize_date(value):
    if not value:
        return None

    value = str(value).strip()
    value = re.sub(r"[.\-]", "/", value)

    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%b/%y", "%d/%b/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def clean_text_value(value):
    if not value:
        return None

    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[\u0600-\u06FF]+", "", value)
    value = re.sub(r"[\|\[\]\{\}]", " ", value)

    return value.strip(" :-")


def parse_nia_debit_note(text, tables=None):
    data = {}

    raw_text = text or ""
    compact_text = re.sub(r"\s+", " ", raw_text)
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    data["insurer_name"] = "NIA Insurance"
    data["premium_currency"] = "AED"

    # Invoice number - works for both NIA formats
    patterns = [
        r"Tax\s*Invoice\s*No\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"Invoice\s*No\s*[:\-]?\s*([A-Z0-9\-\/]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, raw_text, re.IGNORECASE)
        if m:
            data["invoice_number"] = clean_text_value(m.group(1))
            break

    # Invoice date
    patterns = [
        r"Invoice\s*Date\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"Date\s*[:\-]?\s*([A-Z0-9\-\/]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, raw_text, re.IGNORECASE)
        if m:
            data["invoice_date"] = normalize_date(m.group(1))
            break

    # Insured name / customer name - two formats

    customer = None

    # Priority 1: multiline block after "Insured"
    for i, line in enumerate(lines):
        if re.fullmatch(r"Insured", line.strip(), re.IGNORECASE):
            collected = []

            for candidate in lines[i + 1:i + 8]:
                candidate = clean_text_value(candidate)

                if not candidate:
                    continue

                # stop at next field
                if re.search(
                    r"^(Account\s*No|Invoice\s*No|TRN\s*No|Date|Broker|Policy|Motor\s*Insurance|Tax\s*Invoice)",
                    candidate,
                    re.IGNORECASE,
                ):
                    break

                # skip emirate/location only
                if re.fullmatch(
                    r"(SHARJAH|DUBAI|ABU\s*DHABI|FUJAIRAH|RAS\s*AL\s*KHAIMAH)",
                    candidate,
                    re.IGNORECASE,
                ):
                    continue

                # remove OCR junk
                candidate = re.sub(r"[\u0600-\u06FF]+", "", candidate)
                candidate = re.sub(r"\bE{3,}\b", "", candidate)
                candidate = re.sub(r"\s+", " ", candidate).strip(" :-")

                if len(candidate) >= 3:
                    collected.append(candidate)

            if collected:
                customer = " ".join(collected)
                break

    # Priority 2: same-line Insured
    if not customer:
        m = re.search(
            r"Insured\s+(.+?)\s+(?:Account\s*No|Invoice\s*No|TRN\s*No|Date|Broker|Policy|Motor\s*Insurance)",
            compact_text,
            re.IGNORECASE,
        )

        if m:
            customer = m.group(1)

    # Priority 3: Name field for second NIA format
    if not customer:
        m = re.search(
            r"Name\s*[:\-]?\s*:?\s*([^\n\r]+)",
            raw_text,
            re.IGNORECASE,
        )

        if m:
            customer = m.group(1)

    if customer:
        customer = clean_text_value(customer)
        customer = re.sub(r"[\u0600-\u06FF]+", "", customer)
        customer = re.sub(r"\bE{3,}\b", "", customer)
        customer = re.sub(r"\s+", " ", customer).strip(" :-")

        if len(customer) >= 3:
            data["insured_name"] = customer
    # customer = None

    # for pattern in [
    #     r"Insured\s*[:\-]?\s*([^\n\r]+)",
    #     r"Name\s*[:\-]?\s*:?\s*([^\n\r]+)",
    # ]:
    #     m = re.search(pattern, raw_text, re.IGNORECASE)
    #     if m:
    #         customer = m.group(1)
    #         break

    # if not customer:
    #     for i, line in enumerate(lines):
    #         if re.search(r"\bInsured\b", line, re.IGNORECASE):
    #             for candidate in lines[i + 1:i + 6]:
    #                 if re.search(
    #                     r"(TRN|Account|Broker|Policy|Invoice|Date|P\.O|P\.BOX|Code)",
    #                     candidate,
    #                     re.IGNORECASE,
    #                 ):
    #                     continue

    #                 if re.fullmatch(r"[\d\W]+", candidate):
    #                     continue

    #                 if len(candidate) >= 4:
    #                     customer = candidate
    #                     break

    #         if customer:
    #             break

    # if customer:
    #     customer = clean_text_value(customer)
    #     customer = re.split(
    #         r"(Address|Tax\s*Invoice|Policy|TRN|Account|Broker)",
    #         customer,
    #         flags=re.IGNORECASE,
    #     )[0].strip()

    #     if len(customer) >= 3:
    #         data["insured_name"] = customer

    # Broker name - two formats
    broker = None

    broker_block_match = re.search(
        r"Code\s*.*?(?:\n|\r\n?)+.*?:\s*(.*?)\s*NIA\s*TRN",
        raw_text,
        re.IGNORECASE | re.DOTALL,
    )

    if broker_block_match:
        broker_text = broker_block_match.group(1)
        broker_text = broker_text.replace("\n", " ").replace("\r", " ")
        broker_text = clean_text_value(broker_text)
        broker_text = re.sub(r"^\d+\-?", "", broker_text)
        broker_text = re.sub(r"\(\d+\)", "", broker_text)
        broker_text = re.sub(r"\bONLINE\b", "", broker_text, flags=re.I)
        broker_text = re.sub(r"\bMOTOR\b", "", broker_text, flags=re.I)
        broker_text = clean_text_value(broker_text)

        if broker_text and "PROMISE" in broker_text.upper():
            broker = "PROMISE INSURANCE SERVICES LLC"
        else:
            broker = broker_text

    if not broker:
        m = re.search(
            r"Broker\s*[:\-]?\s*(.+)",
            raw_text,
            re.IGNORECASE,
        )
        if m:
            broker = clean_text_value(m.group(1))

    if broker:
        data["broker_name"] = broker

    # Policy number
    policy_number = None

    m = re.search(
        r"Policy\s*(?:No|Number)\s*[:\-]?\s*([A-Z0-9\/\-]+)",
        raw_text,
        re.IGNORECASE,
    )

    if m:
        candidate = m.group(1).strip()
        if len(candidate) >= 6:
            policy_number = candidate

    if not policy_number:
        for i, line in enumerate(lines):
            if re.search(r"Policy\s*(No|Number)", line, re.I):
                for candidate in lines[i + 1:i + 8]:
                    candidate = re.sub(r"^[:\-\s]+", "", candidate.strip())

                    if re.fullmatch(r"[A-Z0-9]+[\/\-][A-Z0-9\/\-]+", candidate):
                        policy_number = candidate
                        break

            if policy_number:
                break

    if policy_number:
        policy_number = re.sub(r"[^A-Z0-9\/\-]", "", policy_number)
        data["policy_number"] = policy_number

    # Policy type
    policy_type = None

    for i, line in enumerate(lines):
        if re.search(r"Policy\s*Type", line, re.I):
            for txt in lines[i:i + 5]:
                if ":" in txt:
                    after_colon = txt.split(":", 1)[1].strip()

                    if re.search(
                        r"(MOTOR|COMPREHENSIVE|TPL|THIRD|FIRE|LIFE)",
                        after_colon,
                        re.I,
                    ):
                        policy_type = after_colon
                        break

                if re.fullmatch(r"[A-Z\s&]+", txt) and re.search(
                    r"(MOTOR|COMPREHENSIVE|TPL|THIRD|FIRE|LIFE)",
                    txt,
                    re.I,
                ):
                    policy_type = txt
                    break

            break

    if policy_type:
        data["policy_type"] = clean_text_value(policy_type)

    # Policy period
    m = re.search(
        r"(Policy\s*Period|Period\s*of\s*Insurance)\s*[:\-]?\s*"
        r"([0-9]{1,2}[\/\-][A-Za-z0-9]{1,}[\/\-][0-9]{2,4})\s*(?:to|TO|-)\s*"
        r"([0-9]{1,2}[\/\-][A-Za-z0-9]{1,}[\/\-][0-9]{2,4})",
        compact_text,
        re.IGNORECASE,
    )

    if m:
        data["policy_start_date"] = normalize_date(m.group(2))
        data["policy_end_date"] = normalize_date(m.group(3))

    # Amounts - V2 format
    net_premium = None
    vat_amount = None
    total = None

    m = re.search(
        r"Taxable\s*Amount\(AED\).*?([\d,]+\.\d{2})",
        compact_text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        net_premium = clean_amount(m.group(1))

    m = re.search(
        r"VAT\s*Amount\(AED\).*?([\d,]+\.\d{2})",
        compact_text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        vat_amount = clean_amount(m.group(1))

    m = re.search(
        r"Total\(AED\).*?([\d,]+\.\d{2})",
        compact_text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        total = clean_amount(m.group(1))

    # Amounts - legacy/fallback format
    if total is None:
        amounts = re.findall(r"([\d,]+\.\d{2})", compact_text)
        cleaned = [clean_amount(a) for a in amounts if clean_amount(a) is not None]

        if len(cleaned) >= 3:
            net_premium = cleaned[-3]
            vat_amount = cleaned[-2]
            total = cleaned[-1]

    data["net_premium"] = net_premium
    data["vat_amount"] = vat_amount

    data["total_amount"] = total
    data["total"] = total
    data["total_premium"] = total
    data["net_due"] = total

    return data