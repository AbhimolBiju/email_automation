from datetime import datetime
import re


# =========================================================
# FIELD VALIDATORS
# =========================================================

def validate_license_number(value):

    if not value:
        return False, "License number missing"

    value = str(value).strip().upper()

    if len(value) < 5:
        return False, "License number too short"

    if len(value) > 20:
        return False, "License number too long"

    if not re.search(r"\d", value):
        return False, "License number must contain digits"

    if not re.fullmatch(r"[A-Z0-9\-]+", value):
        return False, "Invalid license number format"

    return True, None


def validate_name(value):

    if not value:
        return False, "Name missing"

    value = value.strip()

    if len(value.split()) < 2:
        return False, "Invalid full name"

    if not re.fullmatch(r"[A-Za-z\s]+", value):
        return False, "Invalid name characters"

    return True, None


def validate_nationality(value):

    if not value:
        return False, "Nationality missing"

    if len(value.strip()) < 2:
        return False, "Invalid nationality"

    return True, None


def validate_date(value, field_name="date"):

    if not value:
        return False, f"{field_name} missing"

    try:

        datetime.strptime(
            value,
            "%d/%m/%Y"
        )

        return True, None

    except:

        return False, f"Invalid {field_name} format"


def validate_place(value):

    if not value:
        return False, "Place of issue missing"

    if len(value.strip()) < 2:
        return False, "Invalid place of issue"

    return True, None


def validate_traffic_code(value):

    if not value:
        return False, "Traffic code missing"

    value = str(value).strip()

    if not re.fullmatch(r"\d{5,15}", value):

        return False, "Invalid traffic code"

    return True, None


# =========================================================
# MAIN VALIDATION
# =========================================================

def validate_driving_license(
    data,
    side="front"
):

    errors = {}

    # =====================================================
    # FRONT SIDE VALIDATION
    # =====================================================

    if side == "front":

        validators = {

            "license_no": validate_license_number,

            "name": validate_name,

            "nationality": validate_nationality,

            "date_of_birth": lambda v:
                validate_date(v, "date_of_birth"),

            "issue_date": lambda v:
                validate_date(v, "issue_date"),

            "expiry_date": lambda v:
                validate_date(v, "expiry_date"),

            "place_of_issue": validate_place,

        }

    # =====================================================
    # BACK SIDE VALIDATION
    # =====================================================

    else:

        validators = {

            "traffic_code": validate_traffic_code

        }

    # =====================================================
    # RUN VALIDATION
    # =====================================================

    for field, validator in validators.items():

        value = data.get(field)

        is_valid, message = validator(value)

        if not is_valid:

            errors[field] = message

    # =====================================================
    # DATE LOGIC VALIDATION
    # =====================================================

    if side == "front":

        dob = data.get("date_of_birth")

        issue = data.get("issue_date")

        expiry = data.get("expiry_date")

        try:

            dob_date = datetime.strptime(
                dob,
                "%d/%m/%Y"
            ) if dob else None

            issue_date = datetime.strptime(
                issue,
                "%d/%m/%Y"
            ) if issue else None

            expiry_date = datetime.strptime(
                expiry,
                "%d/%m/%Y"
            ) if expiry else None

            if dob_date and issue_date:

                if dob_date >= issue_date:

                    errors["date_order"] = (
                        "DOB cannot be after issue date"
                    )

            if issue_date and expiry_date:

                if expiry_date <= issue_date:

                    errors["expiry_date"] = (
                        "Expiry date must be after issue date"
                    )

        except:
            pass

    return errors


# =========================================================
# VALID / INVALID STATUS
# =========================================================

def is_driving_license_valid(
    data,
    side="front"
):

    errors = validate_driving_license(
        data=data,
        side=side
    )

    return len(errors) == 0

# =========================================================
# CONFIDENCE CALCULATION
# =========================================================

def calculate_driving_license_confidence(
    data,
    validation_errors=None
):

    validation_errors = validation_errors or {}

    confidence = {}

    for field, value in data.items():

        # INVALID FIELD
        if field in validation_errors:

            confidence[field] = 0.0
            continue

        # EMPTY FIELD
        if not value:

            confidence[field] = 0.0
            continue

        # LICENSE NUMBER
        if field == "license_no":

            if re.fullmatch(
                r"[A-Z0-9\-]{5,20}",
                str(value)
            ):

                confidence[field] = 95.0

            else:

                confidence[field] = 50.0

        # NAME
        elif field == "name":

            words = str(value).split()

            if 2 <= len(words) <= 6:

                confidence[field] = 90.0

            else:

                confidence[field] = 60.0

        # NATIONALITY
        elif field == "nationality":

            confidence[field] = 85.0

        # DATES
        elif field in [

            "date_of_birth",
            "issue_date",
            "expiry_date"

        ]:

            try:

                datetime.strptime(
                    value,
                    "%d/%m/%Y"
                )

                confidence[field] = 90.0

            except:

                confidence[field] = 40.0

        # PLACE
        elif field == "place_of_issue":

            confidence[field] = 85.0

        # TRAFFIC CODE
        elif field == "traffic_code":

            if re.fullmatch(
                r"\d{5,15}",
                str(value)
            ):

                confidence[field] = 95.0

            else:

                confidence[field] = 50.0

        else:

            confidence[field] = 80.0

    # =====================================================
    # OVERALL CONFIDENCE
    # =====================================================

    if confidence:

        overall_confidence = round(

            sum(confidence.values()) / len(confidence),

            1

        )

    else:

        overall_confidence = 0.0

    confidence["overall_confidence"] = overall_confidence

    return confidence, overall_confidence