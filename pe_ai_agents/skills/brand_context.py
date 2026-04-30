"""Brand-context skill -- builds a ResolvedContext for this repo.

Each brand-indication repo ships its own ``BRAND_SPEC`` constant so there
is no ambiguity about which brand the harness is operating on. The
resolver enforces:

  - the brand of the running repo matches the spec,
  - the requested ``run_type`` is one this brand supports,
  - the requested ``env`` is one of {predev, dev, prod}.

For ``pe-ai-tremfya-derm`` this resolves to TREMFYA / IQVIA / (pso, psa).
The repo unit is the **jointly-trained model boundary**, not a single
ICD-code family: PsO and PsA are co-trained in
``conf/tremfya/data_science/insights/`` (``model_indications: [pso, psa]``)
and produce one ``tremfya_pso_psa_frm_pkl_file`` artifact, so they live
in the same repo. UC + CD are the analogous joint-model unit (FRM model,
``model_indications: [uc, cd]``) and live in the sibling
``pe-ai-tremfya-gi`` repo.

In production the spec can be loaded from
``conf/{brand}/data_engineering/globals.yml``. For the walking skeleton
we keep the canonical values inline so tests run with no PE.AI codebase
on disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from pe_ai_agents.models.context import ResolvedContext, new_run_id


class BrandMismatch(ValueError):
    """Raised when the caller asks for a brand this repo does not serve."""


@dataclass(frozen=True)
class BrandSpec:
    brand: str
    indication: str
    sub_indications: tuple[str, ...]
    product: str
    data_source: str
    fulfillment_window_days: int
    valid_run_types: tuple[str, ...]


# This repo's identity. Hard-coded so a Tremfya-Derm operator cannot
# accidentally point this harness at the GI or Oncology pipeline.
BRAND_SPEC = BrandSpec(
    brand="tremfya",
    indication="derm",
    sub_indications=("pso", "psa"),
    product="TREMFYA",
    data_source="IQVIA",
    fulfillment_window_days=84,
    valid_run_types=("tremfya", "all_hcps", "persistence", "case_manager"),
)

_VALID_ENVS = ("predev", "dev", "prod")
_DEFAULT_LOOKBACK_DAYS = 18 * 30  # ~18 months


def resolve(
    *,
    run_type: str | None = None,
    env: str = "predev",
    today: date | None = None,
    run_id: str | None = None,
) -> ResolvedContext:
    """Build a ResolvedContext for this repo's brand+indication.

    ``run_type`` defaults to the brand name when omitted. ``today`` is
    injectable so tests can pin the date window deterministically.
    """
    rt = run_type or BRAND_SPEC.brand
    if rt not in BRAND_SPEC.valid_run_types:
        raise BrandMismatch(
            f"run_type {rt!r} not valid for {BRAND_SPEC.brand}-{BRAND_SPEC.indication}; "
            f"expected one of {BRAND_SPEC.valid_run_types}"
        )
    if env not in _VALID_ENVS:
        raise BrandMismatch(
            f"env {env!r} invalid; expected one of {_VALID_ENVS}"
        )

    today = today or date.today()
    return ResolvedContext(
        brand=BRAND_SPEC.brand,
        indication=BRAND_SPEC.indication,
        sub_indications=BRAND_SPEC.sub_indications,
        run_type=rt,
        env=env,
        data_start=today - timedelta(days=_DEFAULT_LOOKBACK_DAYS),
        data_end=today,
        product=BRAND_SPEC.product,
        data_source=BRAND_SPEC.data_source,
        fulfillment_window_days=BRAND_SPEC.fulfillment_window_days,
        run_id=run_id or new_run_id(),
    )
