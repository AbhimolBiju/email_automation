from __future__ import annotations

import os

from django.core.management.base import BaseCommand

from insurance.models import InsuranceProvider


PROVIDER_SEEDS = [
    {
        "code": "DIC",
        "defaults": {
            "name": "DIC",
            "base_url": "https://uatbrokerportal.dubins.ae",
            "username": "PROMISE_API",
            "password": "Prom#26@1SE",
            "timeout": 30,
            "priority": 10,
            "is_active": True,
            "provider_class": "dic_provider.DICProvider",
            "extra_config": {},
        },
    },
    {
        "code": "QIC",
        "defaults": {
            "name": "QIC",
            "base_url": "https://www.devapi.anoudapps.com",
            "username": "promise_api",
            "password": "promise_api#2026$",
            "timeout": 30,
            "priority": 20,
            "is_active": True,
            "provider_class": "qic_provider.QICProvider",
            "extra_config": {
                "company_code": "002",
                "bayanaty_username": "online",
                "bayanaty_password": "online123",
            },
        },
    },
    {
        "code": "NIA",
        "defaults": {
            "name": "NIA",
            "base_url": "http://194.170.131.42:78",
            "username": "amir.basha@promiseinsure.com",
            "password": "Mfapidxb!2025",
            "timeout": 30,
            "priority": 30,
            "is_active": True,
            "provider_class": "nia_provider.NIAProvider",
            "extra_config": {
                "login_mode": "EMAIL",
                "user_id": "amir.basha@promiseinsure.com",
                "business_channel_code": "101",
                "partner_code": "201001",
                "party_code": "201001",
                "division_code": "813",
                "department_code": "10",
            },
        },
    },
]


class Command(BaseCommand):
    help = "Seed or update InsuranceProvider rows for DIC, QIC, and NIA using local integration materials."

    def handle(self, *args, **options):
        for seed in PROVIDER_SEEDS:
            existing = InsuranceProvider.objects.filter(code=seed["code"]).first()
            defaults = dict(seed["defaults"])
            if seed["code"] == "NIA":
                defaults["base_url"] = (
                    os.environ.get("NIA_BASE_URL")
                    or (existing.base_url if existing and existing.base_url else defaults.get("base_url", ""))
                )
            provider, created = InsuranceProvider.objects.update_or_create(
                code=seed["code"],
                defaults=defaults,
            )
            action = "Created" if created else "Updated"
            self.stdout.write(
                f"{action} provider {provider.code} with base_url={provider.base_url}"
            )
            if provider.code == "NIA" and not provider.base_url:
                self.stdout.write(
                    self.style.WARNING(
                        "NIA base_url was not found in the local source bundle. "
                        "Seeded credentials/config, but base_url still needs confirmation."
                    )
                )
