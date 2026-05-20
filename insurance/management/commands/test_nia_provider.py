from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.utils import OperationalError

from insurance.models import InsuranceProvider
from insurance.providers.factory import build_provider


class Command(BaseCommand):
    help = "Test NIA provider authentication, health check, and optional quote flow."

    def add_arguments(self, parser):
        parser.add_argument("--provider-id", type=int)
        parser.add_argument("--quote-payload", type=str)
        parser.add_argument("--skip-auth", action="store_true")

    def handle(self, *args, **options):
        try:
            queryset = InsuranceProvider.objects.filter(code__iexact="NIA")
        except OperationalError as exc:
            raise CommandError("Insurance provider tables are not available yet. Run migrations first.") from exc

        if options.get("provider_id"):
            queryset = queryset.filter(id=options["provider_id"])

        provider_config = queryset.order_by("priority", "name").first()
        if provider_config is None:
            raise CommandError("No NIA provider configuration found.")

        provider = build_provider(provider_config)
        result = {"provider": provider_config.code, "base_url": provider.get_base_url()}

        if not options["skip_auth"]:
            try:
                result["auth"] = {"ok": bool(provider.authenticate())}
                result["health"] = provider.health_check()
            except Exception as exc:
                result["auth"] = {"ok": False, "detail": str(exc)}

        quote_payload = options.get("quote_payload")
        if quote_payload:
            parsed_payload = json.loads(quote_payload)
            try:
                result["quote"] = provider.get_quote(parsed_payload).as_dict(include_raw_response=True)
            except Exception as exc:
                result["quote"] = {"ok": False, "detail": str(exc)}

        self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
