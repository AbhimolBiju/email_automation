#!/usr/bin/env python
"""Debug script to inspect QIC masterdata."""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_pro.settings')
django.setup()

from insurance.providers.qic_masterdata import (
    load_cylinder_records,
    load_body_type_records,
    load_regn_location_records,
    load_nationality_records,
)

print("=" * 80)
print("CYLINDER RECORDS (Valid QIC cylinder codes):")
print("=" * 80)
for rec in load_cylinder_records():
    print(f"  Code: {rec['cylinder_code']:<6} Desc: {rec['cylinder_desc']:<20} Long: {rec['cylinder_long_desc']}")

print("\n" + "=" * 80)
print("BODY TYPE RECORDS (Valid QIC body type codes):")
print("=" * 80)
for rec in load_body_type_records():
    print(f"  Code: {rec['body_type_code']:<6} Desc: {rec['body_type_desc']:<30}")

print("\n" + "=" * 80)
print("REGISTRATION LOCATION RECORDS:")
print("=" * 80)
for rec in load_regn_location_records():
    print(f"  Location: {rec['regn_location']:<25} Code: {rec['regn_location_code']}")

print("\n" + "=" * 80)
print("NATIONALITY RECORDS (Sample):")
print("=" * 80)
for i, rec in enumerate(load_nationality_records()):
    if i < 10:
        print(f"  Code: {rec['nationality_code']:<6} Desc: {rec['nationality_desc']}")
    elif i == 10:
        print(f"  ... and {len(load_nationality_records()) - 10} more")
        break
