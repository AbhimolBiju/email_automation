import re
from datetime import datetime
from .utils import clean_lines, clean_amount


def normalize_rak_date(value):
    if not value:
        return None

    value = value.strip()

    for fmt in ("%d-%B-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


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


def parse_rak_credit_note(raw_text):
    data = {}

    lines = clean_lines(raw_text)
    compact_text = " ".join(lines)
    upper_text = compact_text.upper()

    # BASIC
    data["document_type"] = "CREDIT NOTE" if "CREDIT NOTE" in upper_text else None
    data["company_name"] = "RAK INSURANCE" if "RAK INSURANCE" in upper_text else None
    data["is_rak"] = "RAK INSURANCE" in upper_text

    # INVOICE NUMBER
    invoice_no = get_next_value(lines, "Invoice No")
    if invoice_no:
        m = re.search(r"CN-\d{2}-\d{2}-\d{2}-[A-Z]+-\d+", invoice_no)
        if m:
            data["invoice_number"] = m.group()

    if not data.get("invoice_number"):
        m = re.search(r"CN-\d{2}-\d{2}-\d{2}-[A-Z]+-\d+", compact_text)
        if m:
            data["invoice_number"] = m.group()

    # INVOICE DATE
    invoice_date = get_next_value(lines, "Invoice Date")
    if invoice_date:
        m = re.search(r"\d{2}-[A-Za-z]+-\d{4}", invoice_date)
        if m:
            data["invoice_date"] = normalize_rak_date(m.group())

    if not data.get("invoice_date"):
        m = re.search(r"\d{2}-[A-Za-z]+-\d{4}", compact_text)
        if m:
            data["invoice_date"] = normalize_rak_date(m.group())

    # POLICY DATES
    # ---------------------------------------------------
    # POLICY START DATE
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if "POLICY INCEPTION DATE" in line.upper():
            m = re.search(
                r"\d{2}-[A-Za-z]+-\d{4}",
                line,
                re.IGNORECASE,
                )

            # fallback: next few lines only
            if not m:
                nearby_text = " ".join(lines[i + 1:i + 4])

                # do not allow expiry date to be captured as start date
                nearby_text = re.split(
                    r"POLICY EXPIRY DATE|CREDIT NOTE|BRANCH|INVOICE NO",
                    nearby_text,
                    flags=re.IGNORECASE,
                    )[0]

                m = re.search(
                    r"\d{2}-[A-Za-z]+-\d{4}",
                    nearby_text,
                    re.IGNORECASE,
                    )

            if m:
                data["policy_start_date"] = normalize_rak_date(m.group())

            break


    # Policy end date
    for i, line in enumerate(lines):
        if "POLICY EXPIRY DATE" in line.upper():
            m = re.search(
                r"\d{2}-[A-Za-z]+-\d{4}",
                line,
                re.IGNORECASE,
                )

            # fallback: next few lines only
            if not m:
                nearby_text = " ".join(lines[i + 1:i + 6])

                nearby_text = re.split(
                    r"BRANCH|INVOICE NO|INSURED NAME|ACCOUNT NO",
                    nearby_text,
                    flags=re.IGNORECASE,
                    )[0]

                m = re.search(
                    r"\d{2}-[A-Za-z]+-\d{4}",
                    nearby_text,
                    re.IGNORECASE,
                    )

            if m:
                data["policy_end_date"] = normalize_rak_date(m.group())

            break


    # BRANCH
    branch = get_next_value(lines, "Branch")
    if branch:
        data["branch"] = branch

    # INSURED NAME
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if line.upper().strip().startswith("INSURED NAME"):
            insured_parts = []

            if ":" in line:
                value = line.split(":", 1)[1].strip()
                if value:
                    insured_parts.append(value)

            for nxt in lines[i + 1:i + 20]:
                cleaned = nxt.strip()
                upper = cleaned.upper()

                # skip separator colon lines
                if cleaned in [":", ".","..",". ."]:
                   continue

                # skip date lines
                if re.search(r"\d{2}-[A-Za-z]+-\d{4}", cleaned):
                    continue

                # skip Arabic lines
                if re.search(r"[\u0600-\u06FF]", cleaned):
                    continue

                # stop OCR noise / next fields
                if (
                    "PROMISE INSURANCE" in upper
                    or "SERVICES LLC" in upper
                    or "CREDIT NOTE" in upper
                    or "اشعار دائن" in cleaned
                    ):
                    continue

                if(
                    "ACCOUNT NO" in upper
                    or "ACCOUNT NAME" in upper
                    or "ACCOUNT ADDRESS" in upper
                    or "ACCOUNT EXECUTIVE" in upper
                    or "TRN" in upper
                    ):
                    break

                if cleaned:
                   insured_parts.append(cleaned)

            if insured_parts:
                insured_name = " ".join(insured_parts)

                # remove leading colon
                insured_name = re.sub(r"^:\s*", "", insured_name)

                # remove Arabic label and anything after it
                insured_name = re.split(
                    r"اسم المؤمن له",
                    insured_name,
                    flags=re.IGNORECASE
                )[0]               

                # remove customer id
                insured_name = re.sub(
                    r"\b\d{2}-\d{2}-\d+\b",
                    "",
                    insured_name
                    )
                
                # remove standalone dots/colon OCR junk
                insured_name = insured_name.replace(":", " ")
                insured_name = insured_name.replace(".", " ")

                # clean extra spacing
                insured_name = re.sub(r"\s+", " ", insured_name).strip()


                # remove duplicated names
                words = insured_name.split()
                half = len(words) // 2

                if (
                    len(words) % 2 == 0
                    and words[:half] == words[half:]
                ):
                    insured_name = " ".join(words[:half])

                data["insured_name"] = insured_name

            break

    # fallback: full insured name area between Insured Name and Account section
    m = re.search(
        r"Insured Name\s*:?\s*(.+?)(?:Account No|Account Name)",
        compact_text,
        re.IGNORECASE
    )

    if m:
        block = m.group(1)

        # remove customer id
        block = re.sub(r"\b\d{2}-\d{2}-\d+\b", " ", block)

        # remove dates
        block = re.sub(r"\d{2}-[A-Za-z]+-\d{4}", " ", block)

        # remove Arabic
        block = re.sub(r"[\u0600-\u06FF]+", " ", block)

        # remove known OCR noise
        block = re.sub(
            r"PROMISE INSURANCE|SERVICES LLC|CREDIT NOTE|RAK VINYL|BRANCH|INVOICE NO|CN-\d{2}-\d{2}-\d{2}-[A-Z]+-\d+",
            " ",
            block,
            flags=re.IGNORECASE
        )

        block = block.replace(":", " ").replace(".", " ")
        block = re.sub(r"\s+", " ", block).strip()

        # remove invoice numbers
        block = re.sub(
            r"CN-\d{2}-\d{2}-\d{2}-[A-Z]+-\d+",
            " ",
            block,
            flags=re.IGNORECASE
        )

        # remove broken OCR invoice fragments
        block = re.sub(
            r"CN-\s*-+\s*GPD-\d+",
            " ",
            block,
            flags=re.IGNORECASE
        )

        # remove isolated RAK Vinyl noise
        block = re.sub(
            r"\bRAK\s+VINYL\b",
            " ",
            block,
            flags=re.IGNORECASE
        )

        block = re.sub(r"\s+", " ", block).strip()


        candidates = re.findall(
            r"\b[A-Z][A-Z0-9&.,'()/-]*(?:\s+[A-Z0-9&.,'()/-]+){1,8}\b",
            block
        )

        if candidates:
            candidate = max(candidates, key=lambda x: len(x.split()))
            candidate = re.sub(r"\s+", " ", candidate).strip()

        # remove trailing OCR junk
            candidate = re.sub(
                r"\b(CN|GPD|RAK|VINYL)\b",
                " ",
                candidate,
                flags=re.IGNORECASE
            )

            candidate = re.sub(r"\s+", " ", candidate).strip()

            if (
                not data.get("insured_name")
                or len(candidate.split()) > len(data["insured_name"].split())
                or any(word in data.get("insured_name", "").upper() for word in ["RAK", "VINYL", "BRANCH"])
            ):
                data["insured_name"] = candidate

    #exact duplicate cleanup 
    if data.get("insured_name"):
        words = data["insured_name"].split()
        half = len(words) // 2

        if len(words) % 2 == 0 and words[:half] == words[half:]:
            data["insured_name"] = " ".join(words[:half])

    # final insured name partial duplicate cleanup
    if data.get("insured_name"):
        words = data["insured_name"].split()

        for split in range(2, len(words)):
            first = words[:split]
            second = words[split:]

            # if second part is a prefix repeat of first part
            if first[:len(second)] == second:
                data["insured_name"] = " ".join(first)
                break

    # BROKER NAME
    broker = get_next_value(lines, "Account Name")
    if broker:
        broker = broker.replace("L.L.C.", "").replace("LLC", "").strip()
        data["broker_name"] = broker

    if not data.get("broker_name"):
        m = re.search(r"(PROMISE\s+INSURANCE\s+SERVICES)", compact_text, re.IGNORECASE)
        if m:
            data["broker_name"] = m.group(1).strip()

    data["is_promise_broker"] = (
        "PROMISE INSURANCE SERVICES" in data.get("broker_name", "").upper()
    )

    data["broker_validation"] = (
        "VALID" if data["is_promise_broker"] else "NON_PROMISE_BROKER"
    )

    # ACCOUNT NUMBER
    account_no = get_next_value(lines, "Account No")
    if account_no:
        m = re.search(r"\d{2}-\d{2}-\d+", account_no)
        if m:
            data["account_number"] = m.group()

    # BROKER TRN
    m = re.search(r"TRN\s*no\s*:?\s*(\d{15})", compact_text, re.IGNORECASE)
    if m:
        data["broker_tax_registration_number"] = m.group(1)

    # POLICY NUMBER
    m = re.search(r"P/\d{2}/MOT/[A-Z]+/\d{4}/\d+", compact_text, re.IGNORECASE)
    if m:
        data["policy_number"] = m.group()

    # ---------------------------------------------------
    # POLICY TYPE
    # ---------------------------------------------------

    for i, line in enumerate(lines):
        if "POLICY TYPE" in line.upper():
            nearby_text = " ".join(lines[i:i + 6])

            nearby_text = re.split(
                r"\bCurrency\b|\bCommission Due\b|\bCommision Due\b|\bGross Amount\b|\bExchange Rate\b",
                nearby_text,
                flags=re.IGNORECASE
            )[0]

            nearby_text = re.sub(
                r"Policy Type\s*:?",
                "",
                nearby_text,
                flags=re.IGNORECASE
            )

            nearby_text = nearby_text.replace(":", " ").replace(".", " ")
            nearby_text = re.sub(r"\s+", " ", nearby_text).strip()

            if "RAK MOTOR FULL OPTION BROKER" in nearby_text.upper():
                data["policy_type"] = "RAK Motor Full option Broker"
            elif "THIRD PARTY LIABILITY FOR DIRECT-BROKER" in nearby_text.upper():
                data["policy_type"] = "Third Party Liability For Direct-Broker"
            elif nearby_text:
                data["policy_type"] = nearby_text

            break


    # CURRENCY
    currency = get_next_value(lines, "Currency")
    if currency:
        data["currency"] = currency

    if not data.get("currency") and "AED" in upper_text:
        data["currency"] = "AED"

    # COMMISSION / TOTAL
    commission = get_next_value(lines, "Commission Due")
    if commission:
        m = re.search(r"[\d,]+\.\d{2}", commission)
        if m:
            data["commission_amount"] = clean_amount(m.group())

    # line-by-line fallback
    if not data.get("commission_amount"):
        for i, line in enumerate(lines):
            if "COMMISSION DUE" in line.upper() or "COMMISION DUE" in line.upper():
                nearby_text = " ".join(lines[i:i + 5])

                m = re.search(r"[\d,]+\.\d{2}", nearby_text)

                if m:
                    data["commission_amount"] = clean_amount(m.group())
                    break
    # compact text fallback
    if not data.get("commission_amount"):
        m = re.search(
            r"Commis+s?ion\s+Due.*?([\d,]+\.\d{2})\s*AED",
            compact_text,
            re.IGNORECASE,
            )

        if m:
            data["commission_amount"] = clean_amount(m.group(1))


    # Total amount / gross amount

    gross = get_next_value(lines, "Gross Amount")
    if gross:
        m = re.search(r"[\d,]+\.\d{2}", gross)
        if m:
            data["total_amount"] = clean_amount(m.group())

    if not data.get("total_amount"):
        m = re.search(r"Gross Amount\s+.*?AED\s+([\d,]+\.\d{2})", compact_text, re.IGNORECASE)
        if m:
            data["total_amount"] = clean_amount(m.group(1))

    if not data.get("total_amount"):
        m = re.search(
            r"Gross Amount.*?AED\s*([\d,]+\.\d{2})",
            compact_text,
            re.IGNORECASE
            )
        if m:
            data["total_amount"] = clean_amount(m.group(1))

    if not data.get("total_amount") and data.get("commission_amount"):
        data["total_amount"] = data["commission_amount"]

    # if exchange rate got captured as total amount
    if (
        data.get("total_amount") == "1.00"
        and data.get("commission_amount")
    ):
        data["total_amount"] = data["commission_amount"]

    # VAT not shown in this document
    if data.get("total_amount") and not data.get("commission_amount"):
        data["commission_amount"] = data["total_amount"]

    data["vat_amount"] = data.get("vat_amount")

    data["commission_items"] = []

    if data.get("commission_amount"):
        data["commission_items"].append({
            "commission_type": "commission",
            "commission_percentage": None,
            "commission_amount": data["commission_amount"],
        })
        
    return data