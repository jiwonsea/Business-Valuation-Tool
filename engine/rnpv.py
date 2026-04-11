"""Risk-adjusted NPV (rNPV) engine — pure functions for pharma pipeline valuation.

rNPV = Σ (NPV_drug × PoS_drug) - PV(R&D costs)

Each pipeline drug generates a revenue curve:
  - Ramp-up: launch → peak_sales over years_to_peak
  - Plateau: peak_sales for years_at_peak
  - Decline: patent_expiry decline_rate per year until revenue < 5% of peak

The NPV of each drug's cash flow is multiplied by its phase-based
cumulative Probability of Success (PoS).

For already-approved drugs with existing revenue:
  - If existing_revenue >= peak_sales: plateau at existing_revenue, then decline
  - If existing_revenue < peak_sales: ramp from existing to peak, then plateau, then decline
"""

from dataclasses import dataclass, field


# Industry-average cumulative PoS by phase (BIO/QLS Advisors 2024)
PHASE_POS: dict[str, float] = {
    "preclinical": 0.05,
    "phase1": 0.10,
    "phase2": 0.25,
    "phase3": 0.55,
    "filed": 0.85,
    "approved": 1.00,
}


@dataclass
class DrugCashFlow:
    """Per-drug intermediate result."""
    name: str
    phase: str
    indication: str
    peak_sales: int
    success_prob: float
    cash_flows: list[int] = field(default_factory=list)  # Annual after-tax profit stream
    revenue_curve: list[int] = field(default_factory=list)  # Annual revenue (pre-margin)
    npv: int = 0  # Unadjusted NPV
    rnpv: int = 0  # Risk-adjusted NPV


@dataclass
class RNPVResult:
    """Aggregate rNPV result."""
    drug_results: list[DrugCashFlow]
    total_rnpv: int
    r_and_d_cost_pv: int
    pipeline_value: int  # total_rnpv - r_and_d_cost_pv
    existing_revenue_value: int  # Subset of total_rnpv from approved drugs (for reporting only)
    enterprise_value: int  # = pipeline_value (existing_revenue already included in total_rnpv)
    discount_rate: float


def _build_revenue_curve(
    peak_sales: int,
    years_to_peak: int,
    years_at_peak: int,
    patent_expiry_years: int,
    decline_rate: float,
    launch_year_offset: int,
    existing_revenue: int,
) -> list[int]:
    """Build annual revenue projection for a single drug.

    Returns a list of annual revenues starting from year 0 (base year).
    """
    curve: list[int] = []

    # Pre-launch zeros
    for _ in range(max(launch_year_offset, 0)):
        curve.append(0)

    if existing_revenue > 0 and existing_revenue >= peak_sales:
        # Already at or above peak: plateau at existing revenue, then decline
        remaining_plateau = max(years_at_peak, 1)
        for _ in range(remaining_plateau):
            curve.append(existing_revenue)
    elif existing_revenue > 0:
        # On market but still growing (e.g. Wegovy $12.5B → $18B peak)
        # Continue ramp from existing_revenue to peak_sales
        ramp_years = max(years_to_peak, 1)
        ramp_done = round(ramp_years * existing_revenue / peak_sales)
        remaining_ramp = max(ramp_years - ramp_done, 1)
        step = (peak_sales - existing_revenue) / remaining_ramp
        for i in range(1, remaining_ramp + 1):
            curve.append(round(existing_revenue + step * i))
        # Plateau at peak
        for _ in range(years_at_peak):
            curve.append(peak_sales)
    else:
        # Ramp-up phase: linear ramp from 0 to peak
        ramp_years = max(years_to_peak, 1)
        for yr in range(1, ramp_years + 1):
            rev = round(peak_sales * yr / ramp_years)
            curve.append(rev)

        # Plateau
        for _ in range(years_at_peak):
            curve.append(peak_sales)

    # Decline phase (post-patent): decline until < 5% of peak
    # Decline starts from wherever the curve peaked
    if existing_revenue >= peak_sales:
        base_for_decline = existing_revenue
    else:
        base_for_decline = peak_sales
    threshold = max(base_for_decline * 0.05, 1)
    decline = decline_rate / 100
    remaining_years = patent_expiry_years - len(curve)
    rev = base_for_decline
    for _ in range(max(remaining_years, 0)):
        rev = round(rev * (1 - decline))
        if rev < threshold:
            break
        curve.append(rev)

    return curve


def _npv(cash_flows: list[int], discount_rate_pct: float) -> int:
    """Compute NPV of a cash flow series. Year 0 = first element."""
    r = discount_rate_pct / 100
    if r <= 0:
        return sum(cash_flows)
    total = 0.0
    for t, cf in enumerate(cash_flows):
        total += cf / (1 + r) ** t
    return round(total)


def calc_rnpv(
    pipeline: list[dict],
    discount_rate: float,
    r_and_d_cost: int = 0,
    decline_rate: float = 20.0,
    r_and_d_years: int = 5,
    default_margin: float = 0.35,
    tax_rate: float = 0.22,
) -> RNPVResult:
    """Compute rNPV for a pharma pipeline.

    Revenue is converted to after-tax operating profit before NPV calculation:
        profit = revenue × operating_margin × (1 - tax_rate)

    Args:
        pipeline: List of drug dicts with keys matching PipelineDrug fields.
        discount_rate: Discount rate for NPV (%, e.g. 10.0).
        r_and_d_cost: Annual R&D cost (display units). Spread over r_and_d_years.
        decline_rate: Annual revenue decline post-patent (%).
        r_and_d_years: Number of years to project R&D costs.
        default_margin: Default operating margin (0-1) when drug has no override.
        tax_rate: Corporate tax rate for after-tax profit conversion.

    Returns:
        RNPVResult with per-drug and aggregate values.
    """
    drug_results: list[DrugCashFlow] = []
    total_rnpv = 0
    existing_value = 0

    for drug in pipeline:
        name = drug["name"]
        phase = drug.get("phase", "preclinical")
        indication = drug.get("indication", "")
        peak_sales = drug.get("peak_sales", 0)
        years_to_peak = drug.get("years_to_peak", 5)
        years_at_peak = drug.get("years_at_peak", 5)
        patent_expiry_years = drug.get("patent_expiry_years", 15)
        success_prob = drug.get("success_prob")
        launch_year_offset = drug.get("launch_year_offset", 0)
        existing_revenue = drug.get("existing_revenue", 0)

        # Determine PoS
        if success_prob is not None:
            pos = success_prob
        else:
            pos = PHASE_POS.get(phase, 0.10)

        # Drug-level margin override or company default
        drug_margin = drug.get("operating_margin") or default_margin

        # Build revenue curve
        revenue_curve = _build_revenue_curve(
            peak_sales=peak_sales,
            years_to_peak=years_to_peak,
            years_at_peak=years_at_peak,
            patent_expiry_years=patent_expiry_years,
            decline_rate=decline_rate,
            launch_year_offset=launch_year_offset,
            existing_revenue=existing_revenue,
        )

        # Convert revenue → after-tax operating profit
        after_tax_factor = drug_margin * (1 - tax_rate)
        curve = [round(rev * after_tax_factor) for rev in revenue_curve]

        npv_val = _npv(curve, discount_rate)
        rnpv_val = round(npv_val * pos)

        # Approved drugs with existing revenue: separate for reporting
        if phase == "approved" and existing_revenue > 0:
            existing_value += rnpv_val

        total_rnpv += rnpv_val

        drug_results.append(DrugCashFlow(
            name=name,
            phase=phase,
            indication=indication,
            peak_sales=peak_sales,
            success_prob=pos,
            cash_flows=curve,
            revenue_curve=revenue_curve,
            npv=npv_val,
            rnpv=rnpv_val,
        ))

    # PV of R&D costs (annual cost spread over r_and_d_years)
    r_and_d_pv = 0
    if r_and_d_cost > 0:
        rd_flows = [r_and_d_cost] * r_and_d_years
        r_and_d_pv = _npv(rd_flows, discount_rate)

    pipeline_value = total_rnpv - r_and_d_pv

    return RNPVResult(
        drug_results=drug_results,
        total_rnpv=total_rnpv,
        r_and_d_cost_pv=r_and_d_pv,
        pipeline_value=pipeline_value,
        existing_revenue_value=existing_value,
        enterprise_value=pipeline_value,
        discount_rate=discount_rate,
    )
