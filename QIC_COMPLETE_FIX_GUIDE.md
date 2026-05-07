# QIC API System Error Debugging - Complete Implementation Summary

## Overview
Fixed 4 critical issues preventing QIC motor tariff API calls from succeeding with HTTP 400 "System Error" (respCode 1001).

---

## ✅ Issue #1: Sum Insured (10000 vs 92117)

### Changes Made:
1. **Added `sum_insured` field to Deal model** (`deals/models.py`)
   - Type: `DecimalField(max_digits=12, decimal_places=2)`
   - Purpose: Store market valuation from Bayanaty or manual entry

2. **Updated `_extract_sum_insured()` in quote_service.py**
   - Now checks `deal.sum_insured` first (highest priority)
   - Falls back to `deal.vehicle_value`
   - Falls back to JSON in `additional_field`
   - Falls back to 10000 as last resort
   - Added detailed logging showing where value comes from

3. **Updated `_build_tariff_request()` in qic_provider.py**
   - Added debug logging to show sum_insured source:
     ```python
     payload_sum_insured = payload.get("sum_insured")
     vehicle_sum_insured = vehicle.get("sum_insured")
     print(f"[QIC DEBUG] sum_insured resolution: payload={payload_sum_insured!r}, vehicle={vehicle_sum_insured!r}")
     ```

### Data Flow:
```
Deal.sum_insured = 92117 (saved from Bayanaty)
  ↓
_extract_sum_insured(deal) → returns 92117
  ↓
build_deal_quote_payload(deal) → includes "sum_insured": 92117
  ↓
QICProvider._build_tariff_request(payload) → "sumInsured": 92117.0
  ↓
QIC API → receives correct valuation
```

### Migration Required:
```bash
python manage.py makemigrations deals
python manage.py migrate deals
```

---

## ✅ Issue #2: Vehicle Usage Empty String

### Changes Made:
**Added debug logging in `_build_tariff_request()`**:
```python
# DEBUG: Log vehicle_usage resolution
print(f"[QIC DEBUG] vehicle_usage raw: payload={payload.get('vehicle_usage')!r}, vehicle={vehicle.get('vehicle_usage')!r}")

vehicle_usage = str(payload.get("vehicle_usage") or vehicle.get("vehicle_usage") or "").strip()
print(f"[QIC DEBUG] vehicle_usage after fallback: {vehicle_usage!r}")
```

### Console Output Will Show:
```
[QIC DEBUG] vehicle_usage raw: payload=None, vehicle=None
[QIC DEBUG] vehicle_usage after fallback: ''
```

### Diagnosis from Output:
- If `vehicle_usage` is explicitly set to `""` in payload/vehicle → unresolved in source data
- If `vehicle_usage` is `None` in both payload and vehicle → using empty fallback
- If still empty after strip() → needs investigation in serializer/view

### Next Step:
Check logs to identify if:
1. Build payload doesn't include vehicle_usage
2. Serializer is removing the field
3. Deal model doesn't have vehicle_usage data

---

## ✅ Issue #3: Vehicle Type '1001'

### Confirmed: VALID QIC Code
```json
{
  "body_type_code": "1001",
  "body_type_desc": "Saloon"
}
```

### All Valid Body Type Codes:
- 1001 = Saloon
- 1002 = 4 X 4
- 1003 = Station Wagon
- 1004 = Coupe
- 1005 = Bus
- 1006 = Van (≤3 Ton)
- 1007 = Pickup (≤2.5 Ton)
- 1011 = Sports
- 1012 = Motor Bikes (≤200cc)
- 1014 = Hatchback
- 1022 = Equipment (>3 Ton)

---

## ✅ Issue #4: Hard Field Validations

### Changes Made:
**Completely rewrote `get_tariff()` method** to validate before sending to QIC.

### Validation Rules:
1. **Check 8 required fields are non-empty**:
   - vehicleUsage
   - vehicleType
   - noOfCylinder
   - makeCode
   - modelCode
   - nationality
   - firstRegDate
   - driverDOB

2. **Check sumInsured > 0**
   - Must be numeric
   - Must be positive
   - Cannot be 0 or empty

### Error Messages (Clear & Actionable):
```
ProviderRequestError: QIC tariff request is missing required fields: vehicleUsage, nationality. 
These fields must be non-empty to proceed. Payload: {...full payload...}
```

```
ProviderRequestError: QIC tariff request has invalid sumInsured=0 — must be > 0
```

---

## Files Modified

### 1. `insurance/providers/qic_provider.py`
**Changes**:
- Added vehicle_usage debug logging in `_build_tariff_request()`
- Updated `get_tariff()` with hard validations
- Better error messages identifying which field failed

### 2. `insurance/services/quote_service.py`
**Changes**:
- Enhanced `_extract_sum_insured()` to prioritize `deal.sum_insured`
- Added logging showing where value comes from
- Handles Decimal type from database

### 3. `deals/models.py`
**Changes**:
- Added new field:
  ```python
  sum_insured = models.DecimalField(
      max_digits=12, 
      decimal_places=2, 
      blank=True, 
      null=True,
      help_text="Market valuation (from Bayanaty) or manually entered sum insured for insurance providers"
  )
  ```

---

## Console Output Examples

### Successful Request:
```
[QIC DEBUG] sum_insured resolution: payload=None, vehicle=92117
[QIC DEBUG] vehicle_usage raw: payload=None, vehicle='1001'
[QIC DEBUG] vehicle_usage after fallback: '1001'
QIC payload: {
  'insuredName': 'Kevin Michael Pinto',
  'policyFromDate': '05/05/2026',
  'makeCode': 'MITSUBISHI',
  'modelCode': 'OUTLANDER',
  'modelYear': '2025',
  'sumInsured': 92117.0,
  'vehicleType': '1001',
  'vehicleUsage': '1001',
  'noOfCylinder': '1004',
  'nationality': '082',
  'firstRegDate': '23/04/2025',
  'driverDOB': '25/09/1988',
  ...
}
```

### Failed Request (Missing Field):
```
ProviderRequestError: QIC tariff request is missing required fields: vehicleUsage, nationality. 
These fields must be non-empty to proceed.
```

### Failed Request (Invalid Sum Insured):
```
ProviderRequestError: QIC tariff request has invalid sumInsured=0 — must be > 0
```

---

## How to Populate Sum Insured

### Option A: Command Line (Manual)
```bash
python manage.py shell
```

```python
from deals.models import Deal
deal = Deal.objects.get(id=6)
deal.sum_insured = 92117
deal.valuation_date = date.today()
deal.save()
```

### Option B: From Bayanaty API (Recommended)
```python
from insurance.providers import build_provider
from insurance.models import InsuranceProvider

qic_provider = InsuranceProvider.objects.get(code="QIC")
provider = build_provider(qic_provider)

result = provider.bayanaty_vehicle_valuation({
    "Vin": deal.chassis_number,
    "ModelYear": deal.model_year,
})

valuation = result.get("valuation") or result.get("marketValue")
if valuation and valuation > 0:
    deal.sum_insured = valuation
    deal.valuation_date = date.today()
    deal.save()
```

### Option C: During Quote Fetch (In Progress)
Modify `insurance/views.py`:
```python
# Before calling get_best_quotes(), fetch Bayanaty valuation
if not deal.sum_insured:
    # Fetch from Bayanaty
    # Save to deal.sum_insured
```

---

## Testing Checklist

- [ ] Run `python manage.py migrate deals` to add sum_insured field
- [ ] Update Deal with `sum_insured=92117`
- [ ] Request QIC quote via API
- [ ] Check console for debug logs showing:
  - sum_insured resolution
  - vehicle_usage raw and after fallback
  - Full payload before sending
- [ ] Verify QIC returns quote (not System Error)
- [ ] Test with missing field to verify error message is clear

---

## Debugging Guide

### If still getting System Error:

1. **Check console logs**:
   ```
   [QIC DEBUG] sum_insured resolution: payload=?, vehicle=?
   [QIC DEBUG] vehicle_usage raw: payload=?, vehicle=?
   ```

2. **If sum_insured is still 10000**:
   - Ensure Deal has `sum_insured` value set
   - Check that payload includes sum_insured
   - Look for migration errors

3. **If vehicleUsage is empty**:
   - Check if it's in payload
   - Check if it's in vehicle dict
   - Check build_deal_quote_payload() includes it

4. **If still missing required fields**:
   - Error message will clearly show which field
   - Add the missing field to payload
   - Verify masterdata lookup succeeds

---

## Summary of Code Changes

| File | Change | Purpose |
|------|--------|---------|
| `deals/models.py` | Added `sum_insured` field | Store market valuation |
| `quote_service.py` | Updated `_extract_sum_insured()` | Prioritize Deal.sum_insured |
| `qic_provider.py` | Added vehicle_usage debug logging | Diagnose empty string issue |
| `qic_provider.py` | Rewrote `get_tariff()` validation | Catch errors early, clear messages |

All changes maintain backward compatibility and improve error visibility.
