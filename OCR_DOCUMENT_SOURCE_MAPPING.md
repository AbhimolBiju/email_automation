# OCR Document Source Mapping - Complete Guide

---

## 31. Which Field is Taken From Which Document

### Overview: Multi-Document Processing

When a customer/deal has multiple documents uploaded:

```
Customer/Deal Submission
  ↓
Upload Emirates ID → OCR Extract → Extracted Fields (E)
Upload Mulkiya → OCR Extract → Extracted Fields (M)
Upload Driving License → OCR Extract → Extracted Fields (D)
Upload Passport → OCR Extract → Extracted Fields (P)
  ↓
Frontend Receives All 4 Responses
  ↓
Frontend Merges Data with Priority Rules
  ↓
Final Form Populated with Combined Data
```

---

## Part A: Fields Provided by Each Document Type

### EMIRATES ID Document Provides:

| CRM Field          | Data Type | Azure Field                   | Priority | Description                 |
| ------------------ | --------- | ----------------------------- | -------- | --------------------------- |
| `name`             | String    | `Name` / `DocumentNumber`     | ⭐⭐⭐   | Full name of ID holder      |
| `first_name`       | String    | `FirstName`                   | ⭐⭐⭐   | First name                  |
| `last_name`        | String    | `LastName`                    | ⭐⭐⭐   | Last name                   |
| `emirates_id`      | String    | `DocumentNumber` / `IDNumber` | ⭐⭐⭐   | UAE National ID (13 digits) |
| `date_of_birth`    | Date      | `DateOfBirth`                 | ⭐⭐⭐   | Birth date (YYYY-MM-DD)     |
| `gender`           | Enum      | `Sex` / `Gender`              | ⭐⭐     | Male / Female               |
| `nationality`      | String    | `Nationality`                 | ⭐⭐⭐   | Country of citizenship      |
| `id_expiry_date`   | Date      | `DateOfExpiration`            | ⭐⭐⭐   | ID expiry date              |
| `emirate`          | String    | `Region` / `IssuingPlace`     | ⭐⭐     | Issuing emirate             |
| `customer_address` | String    | `Address`                     | ⭐       | Residential address         |
| `customer_city`    | String    | `CountryRegion`               | ⭐       | City/region                 |
| `customer_pincode` | String    | `PostalCode`                  | ⭐       | ZIP/postal code             |

**Who is this data for?**

- Customer/Lead record
- Personal identification
- **NOT vehicle-specific**

---

### MULKIYA Document Provides:

| CRM Field            | Data Type | Parser Field         | Priority | Description                                    |
| -------------------- | --------- | -------------------- | -------- | ---------------------------------------------- |
| `registration_no`    | String    | `registration_no`    | ⭐⭐⭐   | Vehicle plate format (U/19033)                 |
| `plate_code`         | String    | `plate_code`         | ⭐⭐⭐   | Plate letter code (e.g., "U")                  |
| `plate_number`       | String    | `plate_number`       | ⭐⭐⭐   | Plate numeric (e.g., "19033")                  |
| `plate_source`       | String    | `plate_source`       | ⭐⭐⭐   | Emirate issuing plate (Dubai, Abu Dhabi, etc.) |
| `registration_date`  | Date      | `registration_date`  | ⭐⭐⭐   | Vehicle registration date                      |
| `tcf_number`         | String    | `tcf_no`             | ⭐⭐⭐   | Traffic File Number                            |
| `chassis_no`         | String    | `chassis_no`         | ⭐⭐⭐   | Vehicle VIN (17 chars)                         |
| `make_id`            | String    | `make_id`            | ⭐⭐     | Vehicle manufacturer (TOYOTA, FORD, etc.)      |
| `model_id`           | String    | `model_id`           | ⭐⭐     | Vehicle model (CAMRY, CIVIC, etc.)             |
| `model_year`         | Integer   | `model_year`         | ⭐⭐     | Manufacturing year                             |
| `body_type_id`       | String    | `body_type_id`       | ⭐       | Body type (SEDAN, SUV, TRUCK, etc.)            |
| `engine_capacity_id` | String    | `engine_capacity_id` | ⭐       | Engine displacement (2000CC, 1600CC, etc.)     |
| `transmission_id`    | String    | `transmission_id`    | ⭐       | Transmission type (AUTOMATIC, MANUAL)          |
| `owner`              | String    | `owner`              | ⭐⭐     | Vehicle owner name                             |
| `nationality`        | String    | `nationality`        | ⭐       | Owner nationality                              |

**Who is this data for?**

- Deal/Vehicle record (motor_details table)
- Vehicle specifications
- Insurance underwriting
- **NOT personal customer data**

---

### DRIVING LICENSE Document Provides:

| CRM Field           | Data Type | Azure Field              | Priority | Description                 |
| ------------------- | --------- | ------------------------ | -------- | --------------------------- |
| `license_no`        | String    | `LicenseNumber`          | ⭐⭐⭐   | Driver license number       |
| `name`              | String    | `Name`                   | ⭐⭐     | Full name of license holder |
| `first_name`        | String    | `FirstName`              | ⭐⭐     | First name                  |
| `last_name`         | String    | `LastName`               | ⭐⭐     | Last name                   |
| `date_of_birth`     | Date      | `DateOfBirth`            | ⭐⭐     | Birth date                  |
| `license_from_date` | Date      | `DateOfIssue`            | ⭐⭐     | License issue date          |
| `license_to_date`   | Date      | `DateOfExpiration`       | ⭐⭐     | License expiry date         |
| `gender`            | Enum      | `Sex`                    | ⭐⭐     | Male / Female               |
| `nationality`       | String    | `Nationality`            | ⭐       | Driver's nationality        |
| `customer_address`  | String    | `Address`                | ⭐       | Driver's address            |
| `emirate`           | String    | `IssuingPlace`           | ⭐       | License issuing emirate     |
| `tcf_number`        | String    | `TCFNumber` (if present) | ⭐       | Traffic code (sometimes)    |

**Who is this data for?**

- Driver/Customer record
- Licensing validation
- **Personal data (lower priority than Emirates ID)**

---

### PASSPORT Document Provides:

| CRM Field         | Data Type | Parser Field      | Priority | Description                         |
| ----------------- | --------- | ----------------- | -------- | ----------------------------------- |
| `passport_no`     | String    | `passport_no`     | ⭐⭐⭐   | Passport number (unique identifier) |
| `name`            | String    | `name`            | ⭐       | Full name from passport             |
| `first_name`      | String    | `first_name`      | ⭐       | First name from passport            |
| `last_name`       | String    | `last_name`       | ⭐       | Last name from passport             |
| `nationality`     | String    | `nationality`     | ⭐       | Passport issuing country            |
| `date_of_birth`   | Date      | `date_of_birth`   | ⭐       | Birth date from passport            |
| `gender`          | Enum      | `gender`          | ⭐       | Male / Female                       |
| `passport_expiry` | Date      | `passport_expiry` | ⭐⭐     | Passport expiry date                |

**Who is this data for?**

- International customer identification
- Compliance/KYC
- **Lower priority than emirates_id for UAE residents**

---

## Part B: Source-of-Truth Priority Rules

### How Backend Resolves Duplicate Data

When multiple documents provide the same field, the backend uses this priority:

```
Priority Order (Highest → Lowest):
1. Emirates ID (ID document - most authoritative for UAE)
2. Driving License (Licensing authority)
3. Passport (International ID - lower priority in UAE)
4. Mulkiya (Vehicle registration - not for personal data)
```

### Personal Data Source Priority (name, DOB, gender, nationality)

```
✅ BEST SOURCE: Emirates ID
  └─ Reason: UAE government-issued, most accurate for UAE residents

❓ SECONDARY: Driving License
  └─ Reason: Issued by local traffic authority

❌ FALLBACK: Passport
  └─ Reason: Issued abroad, may use different name spelling

❌ NOT USED: Mulkiya
  └─ Reason: Vehicle document, not personal ID
```

### Vehicle Data Source Priority (registration_no, chassis_no, etc.)

```
✅ BEST SOURCE: Mulkiya
  └─ Reason: Official vehicle registration document

❌ NOT USED: Emirates ID / Driving License / Passport
  └─ Reason: These are personal IDs, not vehicle docs
```

### Example Conflict Resolution

**Scenario: User uploads both Emirates ID AND Driving License**

```
Field: "name"

Emirates ID says:    "Ahmed Mohammed Ali"
Driving License says: "Ahmed M. Ali"

RESULT: Use "Ahmed Mohammed Ali" (Emirates ID)
REASON: Emirates ID is more authoritative

Field: "emirates_id"

Emirates ID says:    "784-1234-5678901-2"
Driving License says: <not provided>

RESULT: Use "784-1234-5678901-2" (Emirates ID only source)
```

---

## Part C: Field Categories by Type

### CUSTOMER/PERSONAL DATA FIELDS

(Extracted from ID documents: Emirates ID, Driving License, Passport)

```
Primary Identity:
  - name / first_name / last_name
  - emirates_id (preferred source)
  - passport_no (fallback)
  - date_of_birth

Contact Info:
  - customer_address
  - customer_city
  - customer_pincode

Demographics:
  - gender
  - nationality
  - emirate (issuing emirate)

License Info:
  - license_no (DL specific)
  - license_from_date (DL specific)
  - license_to_date (DL specific)

Expiry Dates:
  - id_expiry_date (from Emirates ID)
  - passport_expiry (from Passport)
  - license_to_date (from Driving License)
```

**Database Storage:** `Lead` model
**Example Fields:** `Lead.name`, `Lead.emirates_id`, `Lead.nationality`

---

### VEHICLE DATA FIELDS

(Extracted from Mulkiya ONLY)

```
Registration:
  - registration_no (e.g., "U/19033")
  - plate_code
  - plate_number
  - plate_source (emirate)
  - registration_date
  - tcf_number (Traffic File Number)

Vehicle Identification:
  - chassis_no (VIN)
  - make_id (manufacturer)
  - model_id (model name)
  - model_year
  - body_type_id
  - engine_capacity_id
  - transmission_id

Owner Info:
  - owner (vehicle owner name)
  - nationality (owner's nationality)
```

**Database Storage:** `Deal` model (motor_details table)
**Example Fields:** `Deal.registration_no`, `Deal.chassis_no`, `Deal.make_id`

---

### INSURANCE/POLICY DATA FIELDS

(Extracted from invoice/policy documents or Mulkiya TCF)

```
Policy Info:
  - policy_number
  - policy_start_date
  - policy_end_date

Insurance Company:
  - insurer_name

Coverage:
  - sum_insured (vehicle value)
  - premium_amount

Traffic/Vehicle:
  - tcf_number (Traffic File Number from Mulkiya)
```

**Database Storage:** `PolicyIssuance` model (insurance app)
**Example Fields:** `PolicyIssuance.policy_number`, `PolicyIssuance.premium_amount`

---

## Part D: Frontend Field → Source Document Mapping

### Master Mapping Table

```
┌────────────────────────────────────────────────────────────────────────────────┐
│           FRONTEND FIELD ← SOURCE DOCUMENT MAPPING                             │
├────────────────────────────────────────────────────────────────────────────────┤

CUSTOMER IDENTITY FIELDS
┌─────────────────────────────────────────────────────────────────────────────┐
Frontend Form Field        │ Source Document  │ Priority │ OCR Extract Field
─────────────────────────────────────────────────────────────────────────────
Full Name                  │ Emirates ID      │ ⭐⭐⭐    │ name
First Name                 │ Emirates ID      │ ⭐⭐⭐    │ first_name
Last Name                  │ Emirates ID      │ ⭐⭐⭐    │ last_name
Emirates ID Number         │ Emirates ID      │ ⭐⭐⭐    │ emirates_id
Passport Number            │ Passport         │ ⭐⭐⭐    │ passport_no
Passport Expiry Date       │ Passport         │ ⭐⭐     │ passport_expiry
Date of Birth              │ Emirates ID      │ ⭐⭐⭐    │ date_of_birth
Gender                     │ Emirates ID      │ ⭐⭐⭐    │ gender
Nationality                │ Emirates ID      │ ⭐⭐⭐    │ nationality
ID Expiry Date             │ Emirates ID      │ ⭐⭐⭐    │ id_expiry_date
─────────────────────────────────────────────────────────────────────────────

DRIVER/LICENSE FIELDS
─────────────────────────────────────────────────────────────────────────────
License Number             │ Driving License  │ ⭐⭐⭐    │ license_no
License Issue Date         │ Driving License  │ ⭐⭐     │ license_from_date
License Expiry Date        │ Driving License  │ ⭐⭐⭐    │ license_to_date
─────────────────────────────────────────────────────────────────────────────

CONTACT & ADDRESS FIELDS
─────────────────────────────────────────────────────────────────────────────
Address                    │ Emirates ID      │ ⭐      │ customer_address
City                       │ Emirates ID      │ ⭐      │ customer_city
Emirate                    │ Emirates ID      │ ⭐⭐     │ emirate
Postal Code                │ Emirates ID      │ ⭐      │ customer_pincode
─────────────────────────────────────────────────────────────────────────────

VEHICLE REGISTRATION FIELDS
┌─────────────────────────────────────────────────────────────────────────────┐
Frontend Form Field        │ Source Document  │ Priority │ OCR Extract Field
─────────────────────────────────────────────────────────────────────────────
Reg Number                 │ Mulkiya          │ ⭐⭐⭐    │ registration_no
Plate Code                 │ Mulkiya          │ ⭐⭐⭐    │ plate_code
Plate Number               │ Mulkiya          │ ⭐⭐⭐    │ plate_number
Plate Source/Emirate       │ Mulkiya          │ ⭐⭐⭐    │ plate_source
Registration Date          │ Mulkiya          │ ⭐⭐⭐    │ registration_date
Traffic File Number (TCF)  │ Mulkiya          │ ⭐⭐⭐    │ tcf_number
─────────────────────────────────────────────────────────────────────────────

VEHICLE IDENTIFICATION FIELDS
─────────────────────────────────────────────────────────────────────────────
Chassis Number (VIN)       │ Mulkiya          │ ⭐⭐⭐    │ chassis_no
Vehicle Make               │ Mulkiya          │ ⭐⭐     │ make_id
Vehicle Model              │ Mulkiya          │ ⭐⭐     │ model_id
Model Year                 │ Mulkiya          │ ⭐⭐     │ model_year
Body Type                  │ Mulkiya          │ ⭐      │ body_type_id
Engine Capacity            │ Mulkiya          │ ⭐      │ engine_capacity_id
Transmission Type          │ Mulkiya          │ ⭐      │ transmission_id
─────────────────────────────────────────────────────────────────────────────

VEHICLE OWNER FIELDS
─────────────────────────────────────────────────────────────────────────────
Vehicle Owner Name         │ Mulkiya          │ ⭐⭐     │ owner
Owner Nationality          │ Mulkiya          │ ⭐      │ nationality
─────────────────────────────────────────────────────────────────────────────

INSURANCE/POLICY FIELDS
─────────────────────────────────────────────────────────────────────────────
Policy Number              │ Invoice/Mulkiya  │ ⭐⭐⭐    │ policy_number
Policy Start Date          │ Invoice          │ ⭐⭐     │ policy_start_date
Policy End Date            │ Invoice          │ ⭐⭐     │ policy_end_date
Insurer Name               │ Invoice          │ ⭐⭐     │ insurer_name
Sum Insured                │ Invoice/Mulkiya  │ ⭐⭐     │ sum_insured
Premium Amount             │ Invoice          │ ⭐⭐     │ premium_amount
─────────────────────────────────────────────────────────────────────────────
```

---

## Part E: How Backend Combines Multiple Document Data

### Current Implementation

Your backend **does NOT automatically combine** data from multiple uploads.

Instead:

**Per-Upload Response:**

```
Each document upload returns OCR extracted fields for THAT document only:

POST /api/ocr/extract/ with mulkiya.pdf
→ Response with: registration_no, plate_code, chassis_no, etc.

POST /api/ocr/extract/ with emirates_id.pdf
→ Response with: name, emirates_id, date_of_birth, etc.

POST /api/ocr/extract/ with driving_license.pdf
→ Response with: license_no, license_to_date, etc.
```

**Frontend Merges Responses:**

```javascript
// Frontend calls OCR endpoint 3+ times (one per document)
const emiratesResponse = await uploadOCR(emiratesFile, "emirates_id");
const mulkiyaResponse = await uploadOCR(mulkiyaFile, "mulkiya");
const dlResponse = await uploadOCR(dlFile, "driving_license");

// Frontend combines all responses
const combinedData = {
  // From Emirates ID
  name: emiratesResponse.extracted_fields.name,
  emirates_id: emiratesResponse.extracted_fields.emirates_id,
  date_of_birth: emiratesResponse.extracted_fields.date_of_birth,
  nationality: emiratesResponse.extracted_fields.nationality,

  // From Mulkiya
  registration_no: mulkiyaResponse.extracted_fields.registration_no,
  chassis_no: mulkiyaResponse.extracted_fields.chassis_no,
  make_id: mulkiyaResponse.extracted_fields.make_id,

  // From Driving License
  license_no: dlResponse.extracted_fields.license_no,
  license_to_date: dlResponse.extracted_fields.license_to_date,
};

// Frontend auto-fills form with combinedData
setFormState(combinedData);
```

---

### Proposed Future Implementation (Async)

If you convert to async background jobs:

**Single Endpoint to Process All:**

```
POST /api/deals/submit-with-ocr/
Content-Type: multipart/form-data

file_emirates_id=<pdf>
file_mulkiya=<pdf>
file_driving_license=<pdf>

↓

Backend:
  - Queues 3 OCR jobs (one per document)
  - Waits for all to complete
  - Automatically combines results with priority rules
  - Creates Lead + Deal + Policy records
  - Returns job_id with all data

↓

Frontend polls for results
```

**But this is NOT the current implementation.**

---

## Part F: How Deal/Customer Objects Get Populated

### Current Flow: Manual Form Submission

```
Step 1: Upload Documents (Multiple)
  ├─ Upload Emirates ID → OCR → Extract name, emirates_id, dob, etc.
  ├─ Upload Mulkiya → OCR → Extract registration_no, chassis_no, etc.
  └─ Upload Driving License → OCR → Extract license_no, etc.

Step 2: Frontend Receives OCR Responses
  └─ Stores in React state: { extracted_fields, needs_review, confidence }

Step 3: Frontend Auto-Fills Form
  └─ Maps OCR fields to form inputs

Step 4: User Reviews & Corrects
  └─ Edits any incorrect values
  └─ Confirms accuracy

Step 5: User Submits Form
  └─ POST /deals/create/ with merged form data

Step 6: Backend Saves to Database
  ├─ Create/Update Lead record
  │   ├─ name ← from emirates_id OCR
  │   ├─ emirates_id ← from emirates_id OCR
  │   ├─ date_of_birth ← from emirates_id OCR
  │   ├─ gender ← from emirates_id OCR
  │   ├─ nationality ← from emirates_id OCR
  │   └─ address ← from emirates_id OCR
  │
  ├─ Create Deal record (motor_details)
  │   ├─ registration_no ← from mulkiya OCR
  │   ├─ plate_code ← from mulkiya OCR
  │   ├─ chassis_no ← from mulkiya OCR
  │   ├─ make_id ← from mulkiya OCR
  │   ├─ model_id ← from mulkiya OCR
  │   ├─ model_year ← from mulkiya OCR
  │   └─ lead ← ForeignKey to Lead
  │
  └─ Create PolicyIssuance record (optional, if invoice OCR provided)
      ├─ policy_number ← from invoice/mulkiya
      ├─ policy_start_date ← from invoice
      ├─ policy_end_date ← from invoice
      ├─ deal ← ForeignKey to Deal
      └─ insurer_name ← from invoice
```

### Database Schema After Submission

```
Lead (customer record)
├─ id: 101
├─ name: "Ahmed Mohammed Ali" (from emirates_id)
├─ emirates_id: "784-1234-5678901-2" (from emirates_id)
├─ passport_no: "A12345678" (from passport, if provided)
├─ date_of_birth: "1985-06-15" (from emirates_id)
├─ gender: "Male" (from emirates_id)
├─ nationality: "Indian" (from emirates_id)
├─ address: "Dubai, UAE" (from emirates_id)
└─ responsible_user: <staff member>

Deal (motor_details)
├─ id: 42
├─ lead: FK to Lead(101)
├─ registration_no: "U/19033" (from mulkiya)
├─ plate_code: "U" (from mulkiya)
├─ plate_number: "19033" (from mulkiya)
├─ plate_source: "Dubai" (from mulkiya)
├─ chassis_no: "JTHKP5C19E5031234" (from mulkiya)
├─ make_id: "TOYOTA" (from mulkiya)
├─ model_id: "CAMRY" (from mulkiya)
├─ model_year: 2023 (from mulkiya)
├─ tcf_number: "1234567890" (from mulkiya)
└─ stage_id: 2 (Awaiting Additional Documents)

PolicyIssuance (optional)
├─ id: 5
├─ deal: FK to Deal(42)
├─ policy_number: "POLICY-2026-12345" (from invoice/mulkiya)
├─ policy_start_date: "2026-01-01" (from invoice)
├─ policy_end_date: "2027-01-01" (from invoice)
└─ insurer_name: "Allianz" (from invoice)
```

---

## Part G: Document Type Decision Tree

**How Frontend Knows Which Document to Use:**

```
┌─ Customer is from UAE?
│  ├─ YES → Require Emirates ID (primary customer ID)
│  │        Optional: Driving License
│  │        Optional: Mulkiya (if vehicle owner)
│  │        Optional: Passport (for backup/KYC)
│  │
│  └─ NO → Require Passport (international)
│           Optional: Driving License (if has license in UAE)

┌─ Deal is for vehicle insurance?
│  ├─ YES → Require Mulkiya (vehicle registration)
│  │        Extract: registration_no, chassis_no, make, model, year
│  │
│  └─ NO → Skip Mulkiya
│           Focus on personal data only

┌─ Processing new customer?
│  ├─ YES → Upload: Emirates ID + Mulkiya + Driving License
│  │        Priority: Emirates ID for personal data
│  │        Priority: Mulkiya for vehicle data
│  │
│  └─ NO → Update existing customer
│           Only upload documents that changed
```

---

## Part H: Field Override Logic (Conflict Resolution)

### Pseudocode for Frontend Data Merge

```javascript
const mergeOCRData = (emiratesData, mulkiyaData, dlData, passportData) => {
  const merged = {};

  // Personal data: Emirates ID takes priority
  if (emiratesData) {
    merged.name = emiratesData.name || dlData?.name || passportData?.name;
    merged.first_name =
      emiratesData.first_name || dlData?.first_name || passportData?.first_name;
    merged.last_name =
      emiratesData.last_name || dlData?.last_name || passportData?.last_name;
    merged.emirates_id = emiratesData.emirates_id;
    merged.date_of_birth =
      emiratesData.date_of_birth ||
      dlData?.date_of_birth ||
      passportData?.date_of_birth;
    merged.gender =
      emiratesData.gender || dlData?.gender || passportData?.gender;
    merged.nationality =
      emiratesData.nationality ||
      dlData?.nationality ||
      passportData?.nationality;
    merged.id_expiry_date = emiratesData.id_expiry_date;
  } else if (dlData) {
    merged.name = dlData.name || passportData?.name;
    merged.first_name = dlData.first_name || passportData?.first_name;
    merged.last_name = dlData.last_name || passportData?.last_name;
    merged.date_of_birth = dlData.date_of_birth || passportData?.date_of_birth;
    merged.gender = dlData.gender || passportData?.gender;
    merged.nationality = dlData.nationality || passportData?.nationality;
  } else if (passportData) {
    merged.name = passportData.name;
    merged.first_name = passportData.first_name;
    merged.last_name = passportData.last_name;
    merged.date_of_birth = passportData.date_of_birth;
    merged.gender = passportData.gender;
    merged.nationality = passportData.nationality;
  }

  // Passport number: only from passport
  if (passportData) {
    merged.passport_no = passportData.passport_no;
    merged.passport_expiry = passportData.passport_expiry;
  }

  // License data: only from driving license
  if (dlData) {
    merged.license_no = dlData.license_no;
    merged.license_from_date = dlData.license_from_date;
    merged.license_to_date = dlData.license_to_date;
  }

  // Vehicle data: ONLY from mulkiya
  if (mulkiyaData) {
    merged.registration_no = mulkiyaData.registration_no;
    merged.plate_code = mulkiyaData.plate_code;
    merged.plate_number = mulkiyaData.plate_number;
    merged.plate_source = mulkiyaData.plate_source;
    merged.registration_date = mulkiyaData.registration_date;
    merged.tcf_number = mulkiyaData.tcf_number;
    merged.chassis_no = mulkiyaData.chassis_no;
    merged.make_id = mulkiyaData.make_id;
    merged.model_id = mulkiyaData.model_id;
    merged.model_year = mulkiyaData.model_year;
    merged.body_type_id = mulkiyaData.body_type_id;
    merged.engine_capacity_id = mulkiyaData.engine_capacity_id;
    merged.transmission_id = mulkiyaData.transmission_id;
    merged.owner = mulkiyaData.owner;
  }

  // Contact data: from emirates ID (priority)
  if (emiratesData) {
    merged.customer_address =
      emiratesData.customer_address || dlData?.customer_address;
    merged.customer_city = emiratesData.customer_city;
    merged.emirate = emiratesData.emirate || mulkiyaData?.plate_source;
    merged.customer_pincode = emiratesData.customer_pincode;
  }

  return merged;
};

// Usage:
const allData = mergeOCRData(
  emiratesOCRResponse?.extracted_fields,
  mulkiyaOCRResponse?.extracted_fields,
  dlOCRResponse?.extracted_fields,
  passportOCRResponse?.extracted_fields,
);

setFormState(allData);
```

---

## FINAL MASTER TABLE

### Complete Source Document Mapping

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                    FINAL MASTER: FIELD SOURCE MAPPING                                            │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤

CRM Field Name          │ Backend Model  │ Source Document    │ Priority │ Used For
────────────────────────┼────────────────┼────────────────────┼──────────┼────────────────────────
name                    │ Lead           │ Emirates ID        │ ⭐⭐⭐    │ Customer name
first_name              │ Lead           │ Emirates ID        │ ⭐⭐⭐    │ First name
last_name               │ Lead           │ Emirates ID        │ ⭐⭐⭐    │ Last name
emirates_id             │ Deal           │ Emirates ID        │ ⭐⭐⭐    │ National ID
passport_no             │ Lead           │ Passport           │ ⭐⭐⭐    │ International ID
passport_expiry         │ Lead           │ Passport           │ ⭐⭐     │ Passport expiry
date_of_birth           │ Deal           │ Emirates ID        │ ⭐⭐⭐    │ Date of birth
gender                  │ Deal           │ Emirates ID        │ ⭐⭐⭐    │ Gender
nationality             │ Deal           │ Emirates ID        │ ⭐⭐⭐    │ Nationality
customer_address        │ Lead           │ Emirates ID        │ ⭐      │ Address
customer_city           │ Lead           │ Emirates ID        │ ⭐      │ City
emirate                 │ Deal           │ Emirates ID        │ ⭐⭐     │ Emirate
customer_pincode        │ Lead           │ Emirates ID        │ ⭐      │ Postal code
id_expiry_date          │ Deal           │ Emirates ID        │ ⭐⭐⭐    │ ID expiry date
license_no              │ Deal           │ Driving License    │ ⭐⭐⭐    │ License number
license_from_date       │ Deal           │ Driving License    │ ⭐⭐     │ License issue date
license_to_date         │ Deal           │ Driving License    │ ⭐⭐⭐    │ License expiry date
────────────────────────┼────────────────┼────────────────────┼──────────┼────────────────────────
registration_no         │ Deal           │ Mulkiya            │ ⭐⭐⭐    │ Vehicle reg number
plate_code              │ Deal           │ Mulkiya            │ ⭐⭐⭐    │ Plate code
plate_number            │ Deal           │ Mulkiya            │ ⭐⭐⭐    │ Plate number
plate_source            │ Deal           │ Mulkiya            │ ⭐⭐⭐    │ Plate source/emirate
registration_date       │ Deal           │ Mulkiya            │ ⭐⭐⭐    │ Registration date
tcf_number              │ Deal           │ Mulkiya            │ ⭐⭐⭐    │ Traffic file number
chassis_no              │ Deal           │ Mulkiya            │ ⭐⭐⭐    │ Vehicle VIN
make_id                 │ Deal           │ Mulkiya            │ ⭐⭐     │ Vehicle make
model_id                │ Deal           │ Mulkiya            │ ⭐⭐     │ Vehicle model
model_year              │ Deal           │ Mulkiya            │ ⭐⭐     │ Model year
body_type_id            │ Deal           │ Mulkiya            │ ⭐      │ Body type
engine_capacity_id      │ Deal           │ Mulkiya            │ ⭐      │ Engine capacity
transmission_id         │ Deal           │ Mulkiya            │ ⭐      │ Transmission type
owner                   │ Deal           │ Mulkiya            │ ⭐⭐     │ Vehicle owner
────────────────────────┼────────────────┼────────────────────┼──────────┼────────────────────────
policy_number           │ PolicyIssuance │ Invoice/Mulkiya    │ ⭐⭐⭐    │ Policy number
policy_start_date       │ PolicyIssuance │ Invoice            │ ⭐⭐     │ Policy start date
policy_end_date         │ PolicyIssuance │ Invoice            │ ⭐⭐     │ Policy end date
insurer_name            │ PolicyIssuance │ Invoice            │ ⭐⭐     │ Insurance company
sum_insured             │ Deal           │ Invoice/Mulkiya    │ ⭐⭐     │ Vehicle value
premium_amount          │ PolicyIssuance │ Invoice            │ ⭐⭐     │ Premium amount
────────────────────────┼────────────────┼────────────────────┼──────────┼────────────────────────
```

---

## Key Summary

### Document Type Responsibilities

| Document            | Fields Extracted                                                                                                           | Database Target | Role                                  |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------- | --------------- | ------------------------------------- |
| **Emirates ID**     | name, first_name, last_name, emirates_id, date_of_birth, gender, nationality, address, emirate, id_expiry_date             | Lead + Deal     | Primary personal identification       |
| **Mulkiya**         | registration_no, plate_code, chassis_no, make_id, model_id, model_year, tcf_number, owner, plate_source, registration_date | Deal            | Vehicle identification & registration |
| **Driving License** | license_no, license_from_date, license_to_date, name, date_of_birth, gender, nationality                                   | Deal            | Driver license validation             |
| **Passport**        | passport_no, name, date_of_birth, nationality, gender, passport_expiry                                                     | Lead            | International identification (backup) |
| **Invoice**         | policy_number, policy_start_date, policy_end_date, insurer_name, premium_amount, sum_insured                               | PolicyIssuance  | Insurance policy details              |

### Which Database Model Gets Which Data

```
Lead Model Gets:
  - Personal identification (name, emirates_id, passport_no)
  - Demographics (date_of_birth, gender, nationality)
  - Contact info (address, city, emirate)
  - Expiry dates (id_expiry_date, passport_expiry)

Deal Model (motor_details) Gets:
  - Vehicle identification (chassis_no, registration_no, make_id, model_id, model_year)
  - Registration (plate_code, plate_number, plate_source, registration_date, tcf_number)
  - Vehicle owner info (owner name, owner nationality)
  - Personal info for underwriting (emirates_id, date_of_birth, gender, nationality)

PolicyIssuance Model Gets:
  - Policy details (policy_number, policy_start_date, policy_end_date)
  - Insurance details (insurer_name, premium_amount)
```

### Frontend Integration Logic

```
1. User selects document type and uploads file
2. Frontend calls POST /api/ocr/extract/ (one call per document)
3. Backend returns: extracted_fields, needs_review_fields, confidence_scores
4. Frontend stores all responses
5. Frontend merges all responses using priority rules:
   - Personal data priority: Emirates ID > Driving License > Passport
   - Vehicle data: ONLY Mulkiya
   - Policy data: ONLY Invoice
6. Frontend auto-fills form with merged data
7. User corrects any errors (especially needs_review fields)
8. User submits form
9. Backend creates/updates Lead + Deal + PolicyIssuance records
```

This is the complete document source architecture for your OCR system! 🎯
