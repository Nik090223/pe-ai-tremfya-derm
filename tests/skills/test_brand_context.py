"""Brand-context resolver -- spec enforcement + window math."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from pe_ai_agents.skills.brand_context import BRAND_SPEC, BrandMismatch, resolve


def test_resolve_returns_full_context_for_default_run_type() -> None:
    today = date(2026, 4, 28)
    ctx = resolve(env="predev", today=today, run_id="r-1")
    assert ctx.brand == "tremfya"
    assert ctx.indication == "derm"
    assert ctx.sub_indications == ("pso", "psa")
    assert ctx.product == "TREMFYA"
    assert ctx.data_source == "IQVIA"
    assert ctx.fulfillment_window_days == 84
    assert ctx.run_id == "r-1"
    assert ctx.env == "predev"
    assert ctx.data_end == today
    assert ctx.data_start == today - timedelta(days=18 * 30)


def test_resolve_defaults_run_type_to_brand() -> None:
    ctx = resolve()
    assert ctx.run_type == BRAND_SPEC.brand


def test_resolve_rejects_foreign_run_type() -> None:
    with pytest.raises(BrandMismatch):
        resolve(run_type="erleada")


def test_resolve_rejects_invalid_env() -> None:
    with pytest.raises(BrandMismatch):
        resolve(env="staging")


def test_resolve_accepts_alternate_supported_run_types() -> None:
    for rt in ("all_hcps", "persistence", "case_manager"):
        ctx = resolve(run_type=rt, env="dev")
        assert ctx.run_type == rt


def test_is_prod_flips_only_in_prod_env() -> None:
    assert not resolve(env="predev").is_prod()
    assert not resolve(env="dev").is_prod()
    assert resolve(env="prod").is_prod()
