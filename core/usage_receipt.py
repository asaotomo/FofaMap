"""FOFA cost receipts distinguish measured usage, reported charges and unknown billing."""

from __future__ import annotations


def balance_view(account: dict | None) -> dict:
    return {
        key: account[key]
        for key in ("fofa_point", "fcoin", "remain_api_query", "remain_api_data", "remain_api_day", "remain_api_month")
        if account and isinstance(account.get(key), (int, float))
    }


def receipt(
    *, requests: int, fetched: int, returned: int, charged: float | None, before: dict | None = None, after: dict | None = None
) -> dict:
    old, new = balance_view(before), balance_view(after)
    delta = {key: old[key] - new[key] for key in old.keys() & new.keys()}
    return {
        "requests": requests,
        "records_fetched": fetched,
        "records_returned": returned,
        "reported_consumed_fpoint": charged,
        "charge_source": "api_response" if charged is not None else "not_reported",
        "balance_before": old or None,
        "balance_after": new or None,
        "observed_balance_delta": delta or None,
        "billing_note": "Account balances may use free pools, be delayed/cached, or include concurrent activity. "
        "An unchanged balance is not proof of zero cost. Unknown charges are never invented.",
    }
