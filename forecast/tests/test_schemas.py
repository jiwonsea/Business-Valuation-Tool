"""Schema sanity tests — these can run today (no Codex implementation needed)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.models import (
    ScenarioProbabilities,
    SegmentAssumptions,
)


def test_probabilities_must_sum_to_one():
    ScenarioProbabilities(bear=0.25, base=0.50, bull=0.25)  # OK


def test_probabilities_reject_bad_sum():
    with pytest.raises(ValidationError):
        ScenarioProbabilities(bear=0.30, base=0.50, bull=0.30)


def test_segment_assumptions_reject_empty_lists():
    with pytest.raises(ValidationError):
        SegmentAssumptions(
            dram_bit_growth_qoq=[],
            dram_hbm_share_qoq=[0.4],
            dram_hbm_asp_yoy=0.0,
            dram_ddr_asp_qoq=[0.0],
            nand_bit_growth_qoq=[0.0],
            nand_asp_qoq=[0.0],
            other_revenue_growth_qoq=[0.0],
        )
