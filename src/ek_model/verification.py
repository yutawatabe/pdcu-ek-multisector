"""Two-full-solutions versus exact-hat verification certificate."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .model import Equilibrium, HatEquilibrium


@dataclass(frozen=True)
class ObjectComparison:
    max_absolute_error: float
    max_relative_error: float
    tolerance: float
    passed: bool


@dataclass(frozen=True)
class VerificationCertificate:
    comparisons: dict[str, ObjectComparison]
    solver_diagnostics: dict[str, dict[str, object]]
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _compare(actual: np.ndarray, expected: np.ndarray, tolerance: float) -> ObjectComparison:
    absolute = np.abs(np.asarray(actual) - np.asarray(expected))
    relative = absolute / np.maximum(np.abs(np.asarray(expected)), 1e-14)
    max_absolute = float(np.max(absolute))
    max_relative = float(np.max(relative))
    return ObjectComparison(
        max_absolute_error=max_absolute,
        max_relative_error=max_relative,
        tolerance=tolerance,
        passed=bool(max_absolute <= tolerance and max_relative <= tolerance),
    )


def compare_equivalence(
    baseline: Equilibrium,
    counterfactual: Equilibrium,
    hats: HatEquilibrium,
    *,
    tolerance: float = 1e-9,
) -> VerificationCertificate:
    """Compare the levels route with the exact-hat route under one numeraire."""

    full_route = {
        "wage_changes": counterfactual.wages / baseline.wages,
        "price_index_changes": counterfactual.price_indices / baseline.price_indices,
        "counterfactual_trade_shares": counterfactual.trade_shares,
        "real_wage_changes": counterfactual.real_wages / baseline.real_wages,
    }
    hat_route = {
        "wage_changes": hats.wage_hats,
        "price_index_changes": hats.price_hats,
        "counterfactual_trade_shares": hats.counterfactual_trade_shares,
        "real_wage_changes": hats.real_wage_hats,
    }
    comparisons = {
        name: _compare(full_route[name], hat_route[name], tolerance)
        for name in full_route
    }
    diagnostics = {
        "baseline_full": asdict(baseline.diagnostics),
        "counterfactual_full": asdict(counterfactual.diagnostics),
        "exact_hat": asdict(hats.diagnostics),
    }
    all_converged = all(bool(item["converged"]) for item in diagnostics.values())
    passed = bool(all_converged and all(item.passed for item in comparisons.values()))
    return VerificationCertificate(
        comparisons=comparisons,
        solver_diagnostics=diagnostics,
        passed=passed,
    )
