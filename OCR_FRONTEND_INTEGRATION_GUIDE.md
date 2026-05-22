# OCR to Frontend Field Population Complete Guide

---

## 22. Frontend Field Population Flow

### Complete Data Flow Diagram

```
USER UPLOADS DOCUMENT (Mulkiya/Emirates ID/Driving License)
     ↓
HTTP POST to: POST /deals/documents/extract/ (or /api/ocr/extract/)
     ↓
deals/ocr_views.extract_deal_document(request)
     ↓
OCRUploadSerializer Validates:
  - file (PDF/JPG/PNG, max 10MB)
  - document_type (mulkiya, emirates_id, driving_license, etc.)
  - target_schema (deal_create)
     ↓
OCRJob.objects.create(status=PENDING, ...)
     ↓
extract_deal_document_from_upload(file, document_type, target_schema)
     ↓
AzureOCRService.analyze_document() 
  → Azure Prebuilt Model (prebuilt-idDocument / prebuilt-document)
  → returns raw_fields, confidence_scores
     ↓
enrich_raw_fields_for_deal(raw_fields, confidence_scores, document_type)
  → merges parser output with Azure fields
     ↓
extract_document_fields(text, document_type, raw_fields, layout)
  → parse_document() [specific parser: mulkiya_parser, emirates_id_parser, etc.]
  → validate_document()
  → map_document_to_form()
     ↓
map_ocr_fields(ocr_result, target_schema="deal_create")
  → Maps ALL Azure fields → CRM field names
     ↓
filter_by_confidence(mapped_fields)
  → Splits into: high_confidence, needs_review
  → Uses threshold: 0.75 (default)
     ↓
OCRJob.mark_completed(
  extracted_fields={...},
  needs_review_fields={...},
  confidence_scores={...}
)
     ↓
Response Serialized by OCRResultSerializer:
{
  "job_id": 123,
  "extracted_fields": {...},
  "needs_review_fields": {...},
  "confidence_scores": {...}
}
     ↓
HTTP 200 Response to Client
     ↓
FRONTEND API Call Response Received
     ↓
Frontend State Updated:
  - Store extracted_fields in React state
  - Store confidence_scores
  - Store needs_review_fields
     ↓
React Form Component Renders:
  - Auto-populate input fields from extracted_fields
  - Highlight needs_review_fields (yellow/warning)
  - Show confidence_scores (0.0 - 1.0)
     ↓
USER SEES AUTO-FILLED FORM
```

---

## 23. Field Mapping Between Backend and Frontend

### Master Field Mapping Table

```
DOCUMENT TYPE: MULKIYA (Vehicle Registration Card)

Azure/Parser Field Name     | CRM Backend Field  | API Response Key      | Frontend Form Field         | Input Type
---------------------------|-------------------|-----------------------|-----------------------------|-----------
registration_no            | registration_no    | registration_no       | Vehicle Registration Number | Text Input
plate_code                  | plate_code         | plate_code            | Plate Code                  | Text Input
plate_number                | plate_number       | plate_number          | Plate Number                | Text Input
plate_source (emirate)      | plate_source       | plate_source          | Plate Source / Emirate      | Dropdown/Select
tcf_no / traffic_code       | tcf_number         | tcf_number            | Traffic File Number (TCF)   | Text Input
registration_date           | registration_date  | registration_date     | Registration Date           | Date Input
owner / customer_name       | owner              | owner                 | Vehicle Owner Name          | Text Input
nationality                 | nationality        | nationality           | Nationality                 | Text Input
chassis_no / VIN            | chassis_no         | chassis_no            | Chassis Number (VIN)        | Text Input
make_id                     | make_id            | make_id               | Vehicle Make                | Text Input
model_id                    | model_id           | model_id              | Vehicle Model               | Text Input
model_year                  | model_year         | model_year            | Model Year                  | Number Input
body_type_id                | body_type_id       | body_type_id          | Body Type                   | Text Input
engine_capacity_id          | engine_capacity_id | engine_capacity_id    | Engine Capacity             | Text Input
transmission_id            | transmission_id    | transmission_id       | Transmission Type           | Dropdown/Select

---

DOCUMENT TYPE: EMIRATES ID (National ID)

Azure/Parser Field Name     | CRM Backend Field  | API Response Key      | Frontend Form Field         | Input Type
---------------------------|-------------------|-----------------------|-----------------------------|-----------
name / customer_name        | name               | name                  | Full Name                   | Text Input
first_name                  | first_name         | first_name            | First Name                  | Text Input
last_name                   | last_name          | last_name             | Last Name                   | Text Input
DocumentNumber / id_number  | emirates_id        | emirates_id           | Emirates ID Number          | Text Input
DateOfBirth                 | date_of_birth      | date_of_birth         | Date of Birth               | Date Input
DateOfExpiration / expiry   | id_expiry_date     | id_expiry_date        | ID Expiry Date              | Date Input
gender / Sex                | gender             | gender                | Gender                      | Radio/Select
Nationality                 | nationality        | nationality           | Nationality                 | Text Input
Region / IssuingPlace       | emirate            | emirate               | Emirate (Issuing Place)     | Dropdown/Select

---

DOCUMENT TYPE: DRIVING LICENSE

Azure/Parser Field Name     | CRM Backend Field  | API Response Key      | Frontend Form Field         | Input Type
---------------------------|-------------------|-----------------------|-----------------------------|-----------
LicenseNumber / license_no  | license_no         | license_no            | License Number              | Text Input
name / customer_name        | name               | name                  | Full Name                   | Text Input
first_name                  | first_name         | first_name            | First Name                  | Text Input
last_name                   | last_name          | last_name             | Last Name                   | Text Input
DateOfBirth                 | date_of_birth      | date_of_birth         | Date of Birth               | Date Input
DateOfExpiration            | license_to_date    | license_to_date       | License Expiry Date         | Date Input
DateOfIssue                 | license_from_date  | license_from_date     | License Issue Date          | Date Input
gender / Sex                | gender             | gender                | Gender                      | Radio/Select
Nationality                 | nationality        | nationality           | Nationality                 | Text Input
Address                     | customer_address   | customer_address      | Address                     | Text Input
Region / IssuingPlace       | emirate            | emirate               | Emirate                     | Dropdown/Select
```

---

## 24. Auto-Filled Frontend Fields by Document Type

### A. EMIRATES ID Document

**Frontend Fields Auto-Populated:**

1. **Full Name** ← `name` / `customer_name`
2. **First Name** ← `first_name`
3. **Last Name** ← `last_name`
4. **Emirates ID Number** ← `emirates_id` (document number)
5. **Date of Birth** ← `date_of_birth` (formatted as YYYY-MM-DD)
6. **Gender** ← `gender` (normalized to "Male" / "Female")
7. **Nationality** ← `nationality`
8. **ID Expiry Date** ← `id_expiry_date`
9. **Emirate** ← `emirate` (issuing place)

**Confidence Status:**
- High confidence (≥ 0.75): show as auto-filled
- Low confidence (< 0.75): show as "needs review" (yellow highlight)
- Missing (null): leave blank

---

### B. MULKIYA Document (Vehicle Registration)

**Frontend Fields Auto-Populated:**

1. **Vehicle Registration Number** ← `registration_no` (format: ABC/12345)
2. **Plate Code** ← `plate_code` (e.g., "U", "E")
3. **Plate Number** ← `plate_number`
4. **Plate Source / Emirate** ← `plate_source` (e.g., "Dubai", "Abu Dhabi")
5. **Traffic File Number (TCF)** ← `tcf_number`
6. **Registration Date** ← `registration_date`
7. **Vehicle Owner Name** ← `owner`
8. **Nationality** ← `nationality`
9. **Chassis Number (VIN)** ← `chassis_no`
10. **Vehicle Make** ← `make_id`
11. **Vehicle Model** ← `model_id`
12. **Model Year** ← `model_year`
13. **Body Type** ← `body_type_id`
14. **Engine Capacity** ← `engine_capacity_id`
15. **Transmission** ← `transmission_id`

---

### C. DRIVING LICENSE Document

**Frontend Fields Auto-Populated:**

1. **License Number** ← `license_no`
2. **Full Name** ← `name` / `customer_name`
3. **First Name** ← `first_name`
4. **Last Name** ← `last_name`
5. **Date of Birth** ← `date_of_birth`
6. **License Issue Date** ← `license_from_date`
7. **License Expiry Date** ← `license_to_date`
8. **Gender** ← `gender`
9. **Nationality** ← `nationality`
10. **Address** ← `customer_address`
11. **Emirate** ← `emirate`

---

## 25. Exact Data Structures & JSON Examples

### API Request (Frontend → Backend)

```http
POST /deals/documents/extract/ HTTP/1.1
Content-Type: multipart/form-data
Authorization: Bearer <jwt_token>

file=<binary pdf/jpg>
document_type=mulkiya
target_schema=deal_create
```

### API Response (Backend → Frontend) - SUCCESS

**Status Code:** 200 OK

**Response Body:**

```json
{
  "job_id": 42,
  "extracted_fields": {
    "registration_no": "U/19033",
    "plate_code": "U",
    "plate_number": "19033",
    "plate_source": "Dubai",
    "tcf_number": "1234567890",
    "registration_date": "2023-06-15",
    "owner": "Ahmed Mohammed Ali",
    "nationality": "Indian",
    "chassis_no": "JTHKP5C19E5031234",
    "make_id": "TOYOTA",
    "model_id": "CAMRY",
    "model_year": "2023",
    "body_type_id": "SEDAN",
    "engine_capacity_id": "2000CC"
  },
  "needs_review_fields": {
    "transmission_id": "AUTOMATIC"
  },
  "confidence_scores": {
    "registration_no": 0.95,
    "plate_code": 0.92,
    "plate_number": 0.91,
    "plate_source": 0.88,
    "tcf_number": 0.85,
    "registration_date": 0.93,
    "owner": 0.72,
    "nationality": 0.89,
    "chassis_no": 0.87,
    "make_id": 0.78,
    "model_id": 0.81,
    "model_year": 0.95,
    "body_type_id": 0.76,
    "engine_capacity_id": 0.69,
    "transmission_id": 0.62
  }
}
```

### API Response - FAILURE

**Status Code:** 502 Bad Gateway (or appropriate error)

```json
{
  "error_code": "azure_ocr_failed",
  "user_message": "We could not read this document. Try a clearer scan or enter details manually."
}
```

### API Response - VALIDATION ERROR

**Status Code:** 400 Bad Request

```json
{
  "file": ["Only PDF, JPG, and PNG files are supported."],
  "document_type": ["This field may not be blank."],
  "target_schema": ["Unsupported target_schema. Supported: deal_create"]
}
```

---

### Where Each JSON Component is Generated

| JSON Element | Generated In | Reason |
|---|---|---|
| `job_id` | `OCRJob.objects.create()` | Database auto-incremented PK |
| `extracted_fields` | `filter_by_confidence()` returns `high_confidence` bucket | Fields ≥ 0.75 confidence |
| `needs_review_fields` | `filter_by_confidence()` returns `needs_review` bucket | Fields < 0.75 confidence |
| `confidence_scores` | `_extract_fields()` → per-field Azure confidence | Azure SDK + computed average |

### Where This JSON is Stored

**Database:**
```
apps.ocr.models.OCRJob:
  - extracted_fields → JSONField
  - needs_review_fields → JSONField
  - confidence_scores → JSONField
```

**Cache:** Not cached; computed fresh on each request

**Memory:** Only in response; not persisted elsewhere

---

## 26. API Layer Explanation

### Frontend Calls This Endpoint

```
HTTP Method:  POST
Endpoint:     /deals/documents/extract/  or  /api/ocr/extract/
Auth:         IsAuthenticated (JWT Bearer token required)
Content-Type: multipart/form-data
```

### Request Payload Structure

```python
{
  "file": <binary file>,
  "document_type": "mulkiya" | "emirates_id" | "driving_license",
  "target_schema": "deal_create"
}
```

### Response Payload Structure (Success)

```python
{
  "job_id": int,
  "extracted_fields": dict[str, Any],
  "needs_review_fields": dict[str, Any],
  "confidence_scores": dict[str, float]
}
```

### Response Payload Structure (Failure)

```python
{
  "error_code": str,
  "user_message": str
}
```

### Serializers Used

**Request Serializer:**
- `apps.ocr.serializers.OCRUploadSerializer`
  - Validates `file` (extension, size, type)
  - Validates `document_type`
  - Validates `target_schema`

**Response Serializer:**
- `apps.ocr.serializers.OCRResultSerializer` (success)
- `apps.ocr.serializers.OCRErrorSerializer` (error)

### How OCR Data is Exposed to Frontend

**Step 1:** Backend extracts fields in `deals/services/ocr/pipeline.py`

```python
ocr_result, extracted, needs_review, confidence_scores = extract_deal_document_from_upload(...)
```

**Step 2:** View serializes and returns response

```python
response_data = {
    "job_id": job.id,
    "extracted_fields": extracted,
    "needs_review_fields": needs_review,
    "confidence_scores": confidence_scores,
}
return Response(
    OCRResultSerializer(response_data).data,
    status=status.HTTP_200_OK,
)
```

**Step 3:** Frontend receives JSON payload and can use it immediately

---

## 27. Frontend Integration Patterns

### How Frontend Waits for OCR Result

**Pattern 1: Synchronous (Blocking)**
```javascript
// Frontend waits for response
const response = await fetch('/api/ocr/extract/', {
  method: 'POST',
  body: formData,
  headers: { 'Authorization': `Bearer ${token}` }
});

const result = await response.json();
// result contains extracted_fields, needs_review_fields, confidence_scores
```

This is the **current pattern** your backend implements.

**Pattern 2: Asynchronous (Polling)**
```javascript
// If you convert to async background jobs in the future:
const response = await fetch('/api/ocr/extract/', {...});
const { job_id } = await response.json(); // Immediate response with job_id

// Then poll:
while (true) {
  const job = await fetch(`/api/ocr/jobs/${job_id}/`, {...});
  const { status, extracted_fields } = await job.json();
  if (status === 'COMPLETED') break;
  await new Promise(r => setTimeout(r, 1000)); // wait 1 sec
}
```

**Current Flow:** Synchronous blocking (Pattern 1)

### Loading States & UI Feedback

**Frontend Loading Sequence:**

1. **User selects file** → `state.loading = true`, show spinner
2. **POST /api/ocr/extract/** → HTTP request in flight
3. **Azure is processing** → "Reading document..." message
4. **Response received** → `state.loading = false`
5. **Form fields auto-fill** → User sees results instantly

### OCR Success/Failure Handling

**On Success (HTTP 200):**
```javascript
if (response.ok) {
  const { extracted_fields, needs_review_fields, confidence_scores } = result;
  
  // Populate form
  formState.registration_no = extracted_fields.registration_no;
  formState.plate_code = extracted_fields.plate_code;
  // ... etc
  
  // Highlight fields needing review
  reviewFields = Object.keys(needs_review_fields);
  reviewFields.forEach(field => {
    highlightField(field, 'warning'); // Yellow highlight
  });
}
```

**On Failure (HTTP 502 or other):**
```javascript
if (!response.ok) {
  const { error_code, user_message } = result;
  showError(user_message);
  // e.g., "We could not read this document. Try a clearer scan..."
  // form remains unfilled, user enters manually
}
```

### Frontend Decides Which Fields to Populate

**Logic:**

```python
for (field_name, field_value) in extracted_fields.items():
    if field_name in form_field_mapping:  # Is this a known form field?
        input_element = find_input_element(form_field_mapping[field_name])
        input_element.value = field_value
        input_element.disabled = False  # Allow user to edit
```

**If field is in `needs_review_fields`:**
```python
if field_name in needs_review_fields:
    input_element = find_input_element(...)
    input_element.classList.add('needs-review')  # Yellow/warning style
    input_element.value = needs_review_fields[field_name]
```

---

## 28. Missing/Wrong Field Handling

### What Happens if OCR Misses a Field

**Scenario:** OCR extracts 10 fields but skips "chassis_no"

**Backend Response:**
```json
{
  "extracted_fields": {
    "registration_no": "U/19033",
    // ... other fields
    // NOTE: chassis_no is NOT present
  }
}
```

**Frontend Handling:**
```javascript
// If field not in response:
const chassisNo = extracted_fields['chassis_no'] ?? null;
if (chassisNo === null) {
  // Leave input blank
  formState.chassis_no = '';
  // User must enter manually
} else {
  formState.chassis_no = chassisNo;
}
```

### How Frontend Handles Null Values

```javascript
const safeParse = (obj, key, defaultValue = '') => {
  return obj[key] !== null && obj[key] !== undefined ? obj[key] : defaultValue;
};

// Usage:
formState.owner = safeParse(extracted_fields, 'owner', '');
formState.nationality = safeParse(extracted_fields, 'nationality', '');
```

### Incorrect OCR Values in UI

**Example:** OCR reads "ABC/XXXX" instead of "ABC/12345"

**Backend detects low confidence:**
```json
{
  "needs_review_fields": {
    "registration_no": "ABC/XXXX"  // Probably wrong
  },
  "confidence_scores": {
    "registration_no": 0.45  // Below 0.75 threshold
  }
}
```

**Frontend displays:**
```html
<input 
  name="registration_no" 
  value="ABC/XXXX"
  class="needs-review"  <!-- Yellow highlight -->
  style="background-color: #fff3cd;"
/>
<span class="confidence-low">⚠️ Needs review (45% confidence)</span>
```

### Manual Correction Workflow

**User Flow:**

1. OCR populates fields
2. User sees yellow-highlighted fields with low confidence
3. User reads the actual document
4. User manually corrects the value in the input
5. User presses "Save" or "Submit"
6. Corrected value is sent to backend (not via OCR, but via normal form submission)

---

## 29. Complete End-to-End Example

### Scenario: Mulkiya Upload and Auto-Fill

**Step 1: User Action**
```
User clicks "Upload Mulkiya" button
User selects file: mulkiya_scan.pdf
User clicks "Upload"
```

**Step 2: Frontend Uploads**
```javascript
const formData = new FormData();
formData.append('file', file);
formData.append('document_type', 'mulkiya');
formData.append('target_schema', 'deal_create');

const response = await fetch('POST /api/ocr/extract/', {
  method: 'POST',
  body: formData,
  headers: { 'Authorization': `Bearer ${userToken}` }
});
```

**Step 3: Backend Processing**

- `extract_deal_document()` receives request
- `OCRUploadSerializer` validates file is PDF/JPG/PNG, ≤10MB
- `OCRJob` created with status=PENDING
- `analyze_azure_for_deal(file, document_type='mulkiya')`
  - `resolve_model_id('mulkiya')` returns `'prebuilt-document'`
  - Azure SDK calls `DocumentAnalysisClient.begin_analyze_document('prebuilt-document', file_obj)`
  - Azure returns structured fields: `registration_no`, `chassis_no`, etc.
  - Azure also returns full text in `result.content`

- `enrich_raw_fields_for_deal()` merges parser output
  - `extract_document_fields()` parses the OCR text with `mulkiya_parser.py`
  - Parser extracts: `registration_no="U/19033"`, `tcf_number="1234567890"`, `owner="Ahmed Ali"`, etc.
  - Parser finds `registration_date` by regex and label-near heuristics
  - Parser validates dates and formats are correct
  - Merged fields include both Azure structured + parser-enriched fields

- `map_ocr_fields()` maps to CRM schema
  - Takes all raw_fields
  - Maps Azure `DocumentNumber` → CRM `emirates_id`
  - Maps parser `registration_no` → CRM `registration_no`
  - Checks against `FIELD_MAPPING_SCHEMAS['deal_create']['prebuilt-document']`

- `filter_by_confidence()`
  - Fields with confidence ≥ 0.75 → `high_confidence`
  - Fields with confidence < 0.75 → `needs_review`
  - E.g., if owner is extracted by parser but has low OCR confidence → `needs_review`

- `job.mark_completed()`
  - Saves all extracted_fields, needs_review_fields, confidence_scores to DB

**Step 4: Backend Responds**

```json
{
  "job_id": 42,
  "extracted_fields": {
    "registration_no": "U/19033",
    "plate_code": "U",
    "plate_number": "19033",
    "plate_source": "Dubai",
    "tcf_number": "1234567890",
    "registration_date": "2023-06-15",
    "owner": "Ahmed Mohammed Ali",
    "nationality": "Indian",
    "chassis_no": "JTH...1234",
    "make_id": "TOYOTA",
    "model_id": "CAMRY",
    "model_year": "2023"
  },
  "needs_review_fields": {
    "owner": "Ahmed M. Ali"  // Parser extracted with 0.68 confidence
  },
  "confidence_scores": {
    "registration_no": 0.95,
    "plate_code": 0.92,
    "owner": 0.68
  }
}
```

**Step 5: Frontend Receives Response**

```javascript
const result = await response.json();
console.log(result);
// {
//   job_id: 42,
//   extracted_fields: {...},
//   needs_review_fields: {...},
//   confidence_scores: {...}
// }
```

**Step 6: Frontend Auto-Fills Form**

```javascript
// In React component:
const [formState, setFormState] = useState({});

// Handle OCR response
const handleOCRSuccess = (ocrData) => {
  setFormState(prev => ({
    ...prev,
    ...ocrData.extracted_fields,  // Merge high-confidence fields
  }));

  // Store for UI highlighting
  setNeedsReviewFields(Object.keys(ocrData.needs_review_fields));
  setConfidenceScores(ocrData.confidence_scores);
};

handleOCRSuccess(result);
```

**Step 7: User Sees Auto-Filled Form**

```
┌─────────────────────────────────────────────┐
│  Vehicle Registration Details               │
├─────────────────────────────────────────────┤
│                                             │
│  Registration Number:                       │
│  [U/19033]                                  │
│                                             │
│  Plate Code:                                │
│  [U]                                        │
│                                             │
│  Plate Number:                              │
│  [19033]                                    │
│                                             │
│  Plate Source (Emirate):                    │
│  [Dubai]                                    │
│                                             │
│  TCF Number:                                │
│  [1234567890]                               │
│                                             │
│  Registration Date:                         │
│  [2023-06-15]                               │
│                                             │
│  Vehicle Owner: ⚠️ NEEDS REVIEW             │
│  [Ahmed M. Ali]                             │
│  (Confidence: 68% - Please verify)          │
│                                             │
│  Chassis Number:                            │
│  [JTH...1234]                               │
│                                             │
│  Make:                                      │
│  [TOYOTA]                                   │
│                                             │
│  Model:                                     │
│  [CAMRY]                                    │
│                                             │
│  Model Year:                                │
│  [2023]                                     │
│                                             │
│  [Edit Fields] [Save] [Discard]             │
│                                             │
└─────────────────────────────────────────────┘
```

**Step 8: User Reviews & Corrects**

User sees "Vehicle Owner" is highlighted (needs review).

```
Before: [Ahmed M. Ali]
User reads actual document: "Ahmed Mohammed Ali"
After (manual correction): [Ahmed Mohammed Ali]
```

**Step 9: User Submits Form**

User clicks "Save" → form data is sent to `/deals/create/` endpoint (separate from OCR endpoint).

---

## 30. Final Master Mapping Table

### COMPLETE END-TO-END OCR ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                          MULKIYA DOCUMENT - COMPLETE FLOW                                        │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤

Document Feature  │ OCR Extraction Field  │ Backend Database Field │ API Response Key  │ Frontend Input Field    │ UI Component
──────────────────┼──────────────────────┼──────────────────────┼────────────────────┼──────────────────────────┼──────────────
Plate Info        │                      │                      │                    │                          │
  Code            │ plate_code           │ Deal.plate_code*     │ plate_code         │ Plate Code Input         │ Text Input
  Number          │ plate_number         │ NOT on Deal model    │ plate_number       │ Plate Number Input       │ Text Input
  Source/Emirate  │ plate_source         │ Deal.emirate*        │ plate_source       │ Plate Source Dropdown    │ Dropdown
Registration      │                      │                      │                    │                          │
  Reg Number      │ registration_no      │ Deal.reg_number*     │ registration_no    │ Reg Number Input         │ Text Input
  Reg Date        │ registration_date    │ Deal.reg_dt*         │ registration_date  │ Registration Date        │ Date Input
Traffic/TCF       │ tcf_number           │ Deal.tcf_number*     │ tcf_number         │ Traffic File Number      │ Text Input
Vehicle Data      │                      │                      │                    │                          │
  Owner           │ owner                │ NOT on Deal model    │ owner              │ Owner Name Input         │ Text Input
  Nationality     │ nationality          │ Deal.nationality*    │ nationality        │ Nationality Input        │ Text Input
  Chassis/VIN     │ chassis_no           │ Deal.chassis_number* │ chassis_no         │ Chassis Number Input     │ Text Input
  Make            │ make_id              │ Deal.make_id*        │ make_id            │ Vehicle Make Input       │ Text Input
  Model           │ model_id             │ Deal.model_id*       │ model_id           │ Vehicle Model Input      │ Text Input
  Year            │ model_year           │ Deal.model_year*     │ model_year         │ Model Year Input         │ Number Input
  Body Type       │ body_type_id         │ Deal.body_type_id*   │ body_type_id       │ Body Type Input          │ Text Input
  Engine Cap.     │ engine_capacity_id   │ Deal.engine_capacity │ engine_capacity_id │ Engine Capacity Input    │ Text Input
  Transmission    │ transmission_id      │ Deal.transmission_id │ transmission_id    │ Transmission Input       │ Dropdown

* = Existing field on Deal model; some fields are stored in related tables or not persisted to Deal

─────────────────────────────────────────────────────────────────────────────────────────────────────

┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        EMIRATES ID DOCUMENT - COMPLETE FLOW                                      │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤

Document Feature  │ OCR Extraction Field  │ Backend Database Field │ API Response Key  │ Frontend Input Field    │ UI Component
──────────────────┼──────────────────────┼──────────────────────┼────────────────────┼──────────────────────────┼──────────────
Personal Info     │                      │                      │                    │                          │
  Full Name       │ name/customer_name   │ Lead.name*           │ name               │ Full Name Input          │ Text Input
  First Name      │ first_name           │ Lead.first_name      │ first_name         │ First Name Input         │ Text Input
  Last Name       │ last_name            │ Lead.last_name       │ last_name          │ Last Name Input          │ Text Input
  DOB             │ date_of_birth        │ Deal.date_of_birth*  │ date_of_birth      │ Date of Birth            │ Date Input
  Gender          │ gender               │ Deal.gender*         │ gender             │ Gender Radio/Select      │ Radio/Dropdown
ID Info           │                      │                      │                    │                          │
  ID Number       │ emirates_id          │ Deal.emirates_id*    │ emirates_id        │ Emirates ID Input        │ Text Input
  Expiry Date     │ id_expiry_date       │ Deal.id_expiry_dt*   │ id_expiry_date     │ ID Expiry Date           │ Date Input
Location          │                      │                      │                    │                          │
  Emirate         │ emirate              │ Deal.emirate*        │ emirate            │ Emirate Dropdown         │ Dropdown
  Address         │ customer_address     │ Lead.address*        │ customer_address   │ Address Input            │ Text Input
Other             │                      │                      │                    │                          │
  Nationality     │ nationality          │ Deal.nationality*    │ nationality        │ Nationality Input        │ Text Input

─────────────────────────────────────────────────────────────────────────────────────────────────────

┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                      DRIVING LICENSE DOCUMENT - COMPLETE FLOW                                    │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤

Document Feature  │ OCR Extraction Field  │ Backend Database Field │ API Response Key  │ Frontend Input Field    │ UI Component
──────────────────┼──────────────────────┼──────────────────────┼────────────────────┼──────────────────────────┼──────────────
License Info      │                      │                      │                    │                          │
  License Number  │ license_no           │ Deal.license_no*     │ license_no         │ License Number Input     │ Text Input
  Issue Date      │ license_from_date    │ Deal.license_from_dt │ license_from_date  │ License Issue Date       │ Date Input
  Expiry Date     │ license_to_date      │ Deal.license_to_dt*  │ license_to_date    │ License Expiry Date      │ Date Input
Personal Info     │                      │                      │                    │                          │
  Full Name       │ name/customer_name   │ Lead.name*           │ name               │ Full Name Input          │ Text Input
  First Name      │ first_name           │ Lead.first_name      │ first_name         │ First Name Input         │ Text Input
  Last Name       │ last_name            │ Lead.last_name       │ last_name          │ Last Name Input          │ Text Input
  DOB             │ date_of_birth        │ Deal.date_of_birth*  │ date_of_birth      │ Date of Birth            │ Date Input
  Gender          │ gender               │ Deal.gender*         │ gender             │ Gender Radio/Select      │ Radio/Dropdown
Location          │                      │                      │                    │                          │
  Address         │ customer_address     │ Lead.address*        │ customer_address   │ Address Input            │ Text Input
  Emirate         │ emirate              │ Deal.emirate*        │ emirate            │ Emirate Dropdown         │ Dropdown
Other             │                      │                      │                    │                          │
  Nationality     │ nationality          │ Deal.nationality*    │ nationality        │ Nationality Input        │ Text Input

─────────────────────────────────────────────────────────────────────────────────────────────────────
```

---

## Key Architectural Insights

### 1. Data Storage Model

The OCR response is **NOT** automatically saved to `Deal` model.

Instead:
- **OCR Response** is stored in `OCRJob` model (temporary)
- **Frontend** receives the extracted fields
- **Frontend** displays them to user in form
- **User submits form** → data is saved to `Deal` and `Lead` models

This is intentional: OCR provides **suggestions**, not final data.

### 2. Field Mapping Strategy

Your system uses **three-level mapping**:

```
Azure SDK Response
    ↓
apps.ocr.field_mappings.FIELD_MAPPING_SCHEMAS
    ↓
CRM Schema (deal_create)
    ↓
Frontend Form Fields
```

This allows:
- Multiple Azure fields → one CRM field (many-to-one)
- Flexible schema changes without code changes
- Easy addition of new document types

### 3. Confidence Filtering Strategy

Fields are split by confidence threshold (0.75):

**Why two buckets?**
- `extracted_fields`: high-confidence, auto-fill immediately
- `needs_review_fields`: low-confidence, highlight for user verification

This reduces data entry errors while still being fast.

### 4. Frontend Integration Pattern (Current)

The current implementation uses **synchronous blocking**.

When user uploads, frontend:
1. Shows spinner
2. Waits for response (Azure can take 5-30 seconds)
3. Displays results
4. Auto-fills form

**Pros:** Simple, user sees results immediately  
**Cons:** Blocks the HTTP request, slower user experience for large uploads

### 5. Error Recovery

If OCR fails:
- Frontend catches error response
- Shows user-friendly message
- Form remains empty
- User enters data manually

---

## Frontend Implementation Checklist

If you're building the frontend, you need to:

- [ ] Create `/api/ocr/extract` API client function
- [ ] Handle multipart form-data upload with file + metadata
- [ ] Parse response JSON with `extracted_fields`, `needs_review_fields`, `confidence_scores`
- [ ] Map each `extracted_fields` key to corresponding form input
- [ ] Highlight `needs_review_fields` with yellow/warning styling
- [ ] Display confidence scores (optional; UX detail)
- [ ] Allow user to edit any auto-filled field
- [ ] Show error message if OCR fails
- [ ] Implement loading spinner while OCR processes
- [ ] Validate user-corrected values before form submission

---

## Summary

**The complete OCR-to-frontend flow:**

```
User Uploads PDF
  → Backend validates & stores in OCRJob
  → Azure analyzes document
  → Parsers extract structured data
  → Fields are mapped to CRM schema
  → Confidence filter splits high/low
  → API response serialized (JSON)
  → Frontend receives JSON
  → Form inputs auto-populated
  → User sees extracted data + warnings
  → User can edit before submitting
  → Form submit sends corrected data
  → Backend saves to Deal/Lead models
```

All OCR data flows through `OCRJob` and `OCRResultSerializer`.  
All field mapping is configured in `apps.ocr.field_mappings`.  
All parsers are in `deals.services.ocr.parsers`.  
All frontend integration is HTTP-based via JSON.
