import logging
import threading

from django.db import close_old_connections

from insurance.services.quote_service import get_best_quotes

logger = logging.getLogger(__name__)


def _run_quote_generation(deal_id: int, force_refresh: bool, triggered_by_id: int | None) -> None:
    close_old_connections()
    try:
        get_best_quotes(
            deal_id,
            force_refresh=force_refresh,
            triggered_by_id=triggered_by_id,
        )
    finally:
        close_old_connections()


def enqueue_quote_generation(
    deal_id: int,
    *,
    force_refresh: bool = False,
    triggered_by_id: int | None = None,
) -> None:
    thread = threading.Thread(
        target=_run_quote_generation,
        args=(deal_id, force_refresh, triggered_by_id),
        name=f"quote-generation-{deal_id}",
        daemon=True,
    )
    thread.start()
    logger.info("Queued quote generation for deal %s", deal_id)

