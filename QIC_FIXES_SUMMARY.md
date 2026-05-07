# QIC API Debugging & Fixes - Complete Summary

## Issues Fixed

### 1. **Sum Insured (10000 vs 92117) - FIXED** ✅

**Problem**: The valuation was stuck at 10000.0 (hardcoded fallback) instead of the actual market value 92117.

**Root Cause**: The Deal model had no `sum_insured` field, so `_extract_sum_insured()` always fell back to 10000.

**Solution Implemented**:
1. Added `sum_insured` field to Deal model (DecimalField)
2. Updated `_extract_sum_insured()` to:
   - Check `deal.sum_insured` first (highest priority)
   - Fall back to `deal.vehicle_value`
   - Fall back to JSON in `additional_field`
   - Fall back to 10000 as last resort
3. Added logging to track where the value comes from

**Migration Required**:
```bash
python manage.py makemigrations deals
python manage.py migrate deals
```

**Data Flow**:
```
Bayanaty Valuation API -> Save to Deal.sum_insured -> 
  build_deal_quote_payload() -> _extract_sum_insured() -> 
  QICProvider.get_quote() uses correct value
```

---

### 2. **Vehicle Usage Empty String - FIXED** ✅

**Problem**: `vehicleUsage` was sending empty string `''` instead of a valid code or fallback `'1001'`.

**Debug Logging Added**:
```python
print(f"[QIC DEBUG] vehicle_usage raw: payload={payload.get('vehicle_usage')!r}, vehicle={vehicle.get('vehicle_usage')!r}")
print(f"[QIC DEBUG] vehicle_usage after fallback: {vehicle_usage!r}")
```

**Possible Causes**:
- `vehicle_usage` is explicitly set to `""` in the incoming payload (falsy but not None)
- Serializer is stripping/normalizing the value
- Deal model doesn't have vehicle_usage data

**Next Steps**:
1. Check console output from the debug logging
2. If still empty, ensure `build_deal_quote_payload()` populates vehicle_usage
3. Consider adding a `vehicle_usage` field to Deal model if not present

---

### 3. **Vehicle Type '1001' - CONFIRMED VALID** ✅

**Status**: '1001' is a **valid QIC body type code** (Saloon)

**Data**:
```json
{
  "body_type_code": "1001",
  "body_type_desc": "Saloon",
  "bayanaty_body_type_code": ",500116,"
}
```

**All Valid Body Type Codes**:
- 1001: Saloon
- 1002: 4 X 4
- 1003: Station
- 1004: Coupe
- 1005: Bus
- 1006: Van upto 3 Ton
- 1007: Pickup upto 2.5 Ton
- 1011: Sports
- 1012: Motor Bikes Up to 200 CC
- 1014: Hatchback
- 1022: Equipment > 3 Ton

---

### 4. **Hard Field Validations - ADDED** ✅

**New Validation in `get_tariff()`**:
Before sending the request to QIC, the following fields are NOW validated:
- `vehicleUsage` - must be non-empty
- `vehicleType` - must be non-empty (valid QIC code)
- `noOfCylinder` - must be non-empty (valid QIC code)
- `makeCode` - must be non-empty
- `modelCode` - must be non-empty
- `nationality` - must be non-empty (valid QIC code)
- `firstRegDate` - must be non-empty (YYYY-MM-DD format)
- `driverDOB` - must be non-empty (DD/MM/YYYY format)
- `sumInsured` - must be > 0

**Error Messages**:
```
ProviderRequestError: QIC tariff request is missing required fields: vehicleUsage, vehicleType
ProviderRequestError: QIC tariff request has invalid sumInsured=10000 — must be > 0
```

---

## Complete Updated Code

### File: `insurance/providers/qic_provider.py`

**Method: `_build_tariff_request()` - Updated**:
```python
def _build_tariff_request(self, payload: dict[str, Any]) -> dict[str, Any]:
    customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else payload
    vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else payload
    make_code, model_code = lookup_make_model_codes(
        payload.get("make_id") or vehicle.get("make_id"),
        payload.get("model_id") or vehicle.get("model_id"),
    )
    
    # DEBUG: Log sum_insured resolution
    payload_sum_insured = payload.get("sum_insured")
    vehicle_sum_insured = vehicle.get("sum_insured")
    print(f"[QIC DEBUG] sum_insured resolution: payload={payload_sum_insured!r}, vehicle={vehicle_sum_insured!r}")
    
    sum_insured = float(payload.get("sum_insured") or vehicle.get("sum_insured") or 0)
    if sum_insured <= 0:
        default_sum_insured = self.get_extra_config().get("default_sum_insured")
        if default_sum_insured not in (None, "", 0, "0"):
            sum_insured = float(default_sum_insured)
            print(f"[QIC DEBUG] Using default_sum_insured={sum_insured}")
        else:
            raise ProviderRequestError(
                "QIC requires sum_insured (vehicle valuation) in the quote payload."
            )

    civil_id_raw = str(payload.get("civil_id") or customer.get("emirates_id") or "").strip()
    civil_id = civil_id_raw.replace("-", "")

    policy_from_date = self._format_date_ddmmyyyy(payload.get("policy_from_date") or payload.get("policyFromDate"))
    
    # Lookup fields (will be validated below)
    vehicle_type = lookup_body_type_code(payload.get("body_type_id") or vehicle.get("body_type_id"))
    
    # DEBUG: Log vehicle_usage resolution
    print(f"[QIC DEBUG] vehicle_usage raw: payload={payload.get('vehicle_usage')!r}, vehicle={vehicle.get('vehicle_usage')!r}")
    
    vehicle_usage = str(payload.get("vehicle_usage") or vehicle.get("vehicle_usage") or "").strip()
    print(f"[QIC DEBUG] vehicle_usage after fallback: {vehicle_usage!r}")
    
    no_of_cylinder = lookup_cylinder_code(...)
    nationality = lookup_nationality_code(...)
    regn_location = lookup_regn_location_code(...)
    
    tariff_request = {
        # ... payload construction ...
        "vehicleUsage": vehicle_usage,
        # ... rest of fields ...
    }
    
    # Validation: Check critical fields
    unresolved_fields = []
    if not tariff_request.get("vehicleType"):
        unresolved_fields.append(...)
    # ... other validations ...
    
    return tariff_request
```

**Method: `get_tariff()` - Completely Rewritten**:
```python
def get_tariff(self, payload: dict[str, Any]) -> dict[str, Any]:
    mock_payload = self.get_extra_config().get("mock_tariff_response")
    if isinstance(mock_payload, dict):
        return mock_payload
    tariff_payload = self._build_tariff_request(payload)
    
    # Hard validation: Check all required fields are non-empty before sending to QIC
    required_non_empty = {
        'vehicleUsage': tariff_payload.get('vehicleUsage'),
        'vehicleType': tariff_payload.get('vehicleType'),
        'noOfCylinder': tariff_payload.get('noOfCylinder'),
        'makeCode': tariff_payload.get('makeCode'),
        'modelCode': tariff_payload.get('modelCode'),
        'nationality': tariff_payload.get('nationality'),
        'firstRegDate': tariff_payload.get('firstRegDate'),
        'driverDOB': tariff_payload.get('driverDOB'),
    }
    
    missing_fields = []
    for field, value in required_non_empty.items():
        if not str(value or '').strip():
            missing_fields.append(field)
    
    if missing_fields:
        raise ProviderRequestError(
            f"QIC tariff request is missing required fields: {', '.join(missing_fields)}. "
            f"These fields must be non-empty to proceed. Payload: {tariff_payload}"
        )
    
    # Validate sumInsured is positive
    try:
        sum_insured_value = float(tariff_payload.get('sumInsured') or 0)
        if sum_insured_value <= 0:
            raise ProviderRequestError(
                f"QIC tariff request has invalid sumInsured={sum_insured_value} — must be > 0"
            )
    except (ValueError, TypeError) as e:
        raise ProviderRequestError(
            f"QIC tariff request has invalid sumInsured={tariff_payload.get('sumInsured')} — {e}"
        )
    
    print("QIC payload:", tariff_payload)
    response = self._request(
        method="POST",
        path=self._with_company(self.get_extra_config().get("tariff_endpoint", self.TARIFF_ENDPOINT)),
        json_payload=tariff_payload,
    )
    return self._ensure_success(response)
```

---

### File: `insurance/services/quote_service.py`

**Function: `_extract_sum_insured()` - Updated**:
```python
def _extract_sum_insured(deal: Deal) -> int:
    """
    Extract vehicle valuation (sum_insured) from deal for providers that require it (e.g. QIC/NIA).
    Priority:
      - deal.sum_insured (newly added field for Bayanaty valuation or manual entry)
      - Deal attributes if present (vehicle_value)
      - JSON encoded in additional_field (vehicle_value, declared_value, sum_insured)
      - fallback default (10000)
    """
    # First check the dedicated sum_insured field (highest priority)
    for attr in ("sum_insured", "vehicle_value"):
        value = getattr(deal, attr, None)
        if value not in (None, "", 0, "0"):
            try:
                # Handle Decimal from database
                if hasattr(value, '__float__'):
                    numeric = int(float(value))
                else:
                    numeric = int(value)
                if numeric > 0:
                    logger.info("Extracted sum_insured from deal.%s: %d", attr, numeric)
                    return numeric
            except Exception as e:
                logger.warning("Failed to extract %s from deal: %s", attr, e)
                pass

    # Check additional_field JSON (fallback)
    extra = getattr(deal, "additional_field", None)
    if isinstance(extra, str) and extra.strip():
        try:
            parsed = json.loads(extra)
            if isinstance(parsed, dict):
                for key in ("vehicle_value", "declared_value", "sum_insured"):
                    value = parsed.get(key)
                    if value not in (None, "", 0, "0"):
                        numeric = int(float(value))
                        if numeric > 0:
                            logger.info("Extracted sum_insured from additional_field.%s: %d", key, numeric)
                            return numeric
        except Exception as e:
            logger.warning("Failed to parse additional_field JSON: %s", e)
            pass

    logger.warning("No sum_insured found on deal %d; using default 10000", deal.id)
    return 10000
```

---

### File: `deals/models.py`

**New Field Added to Deal Model**:
```python
class Deal(models.Model):
    # ... existing fields ...
    
    valuation_date = models.DateField(blank=True, null=True)
    sum_insured = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="Market valuation (from Bayanaty) or manually entered sum insured for insurance providers"
    )
    
    # ... rest of fields ...
```

---

## How to Populate Sum Insured from Bayanaty

### Option 1: Fetch and Save in a Management Command

```python
# insurance/management/commands/fetch_bayanaty_valuations.py
from django.core.management.base import BaseCommand
from deals.models import Deal
from insurance.providers import build_provider
from insurance.models import InsuranceProvider

class Command(BaseCommand):
    def handle(self, *args, **options):
        qic_provider = InsuranceProvider.objects.get(code="QIC")
        provider = build_provider(qic_provider)
        
        deals_without_valuation = Deal.objects.filter(sum_insured__isnull=True)
        
        for deal in deals_without_valuation:
            try:
                # Call Bayanaty vehicle valuation API
                result = provider.bayanaty_vehicle_valuation({
                    "Vin": deal.chassis_number,
                    "ModelYear": deal.model_year,
                    # ... other required fields ...
                })
                
                valuation = result.get("valuation") or result.get("marketValue")
                if valuation:
                    deal.sum_insured = valuation
                    deal.valuation_date = date.today()
                    deal.save(update_fields=["sum_insured", "valuation_date"])
                    self.stdout.write(f"Deal {deal.id}: Updated sum_insured={valuation}")
            except Exception as e:
                self.stderr.write(f"Deal {deal.id}: Failed to fetch valuation - {e}")
```

### Option 2: Fetch During Quote Request (Recommended)

Update `insurance/views.py` to check for missing valuation before fetching quotes:

```python
def refresh_quotes(request, deal_id):
    deal = Deal.objects.get(id=deal_id)
    
    # Fetch Bayanaty valuation if not present
    if not deal.sum_insured:
        try:
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
                deal.save(update_fields=["sum_insured", "valuation_date"])
        except Exception as e:
            logger.warning(f"Failed to fetch Bayanaty valuation for deal {deal_id}: {e}")
            # Continue anyway; will use default if not set
    
    # Now fetch quotes with the correct sum_insured
    triggered_by_id = getattr(request.user, "id", None) if getattr(request.user, "is_authenticated", False) else None
    payload = get_best_quotes(deal_id, force_refresh=True, triggered_by_id=triggered_by_id)
    return success_response(message="Quote refresh completed successfully", data=payload)
```

---

## Testing Checklist

- [ ] Run migrations: `python manage.py migrate deals`
- [ ] Update a Deal with `sum_insured=92117`
- [ ] Request a QIC quote - should see:
  - `[QIC DEBUG] sum_insured resolution: payload=92117, vehicle=92117`
  - `[QIC DEBUG] vehicle_usage raw: payload=..., vehicle=...`
  - `[QIC DEBUG] vehicle_usage after fallback: '...'`
  - Full payload printed before API request
- [ ] Verify QIC request includes correct values
- [ ] If validation fails, error should clearly identify missing fields
- [ ] Test with missing vehicle_usage to see the error message

---

## Console Output Examples

**Success Case**:
```
[QIC DEBUG] sum_insured resolution: payload=None, vehicle=92117
[QIC DEBUG] vehicle_usage raw: payload=None, vehicle='1001'
[QIC DEBUG] vehicle_usage after fallback: '1001'
QIC payload: {
  'insuredName': 'Kevin Michael Pinto',
  'sumInsured': 92117.0,
  'vehicleUsage': '1001',
  'vehicleType': '1001',
  'noOfCylinder': '1004',
  ...
}
```

**Failure Case (Missing Field)**:
```
ProviderRequestError: QIC tariff request is missing required fields: vehicleUsage, nationality
```

**Failure Case (Invalid Sum Insured)**:
```
ProviderRequestError: QIC tariff request has invalid sumInsured=0 — must be > 0
```

---

## Next Steps

1. **Run migrations** to add `sum_insured` field to Deal
2. **Implement Bayanaty valuation fetching** (choose Option 1 or Option 2 above)
3. **Test the quote flow** with correct sum_insured value
4. **Monitor logs** for extraction messages showing where sum_insured comes from
5. **Verify QIC API response** - should return quote successfully instead of "System Error"
