"""Exact-hat counterfactual solution using baseline equilibrium shares."""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

from .model import Equilibrium, HatEquilibrium, Primitives, SolverDiagnostics, _as_float_array


def solve_exact_hat(
    primitives: Primitives,
    baseline: Equilibrium,
    trade_cost_hat: object,
    *,
    residual_tolerance: float = 1e-11,
    max_evaluations: int = 2_000,
) -> HatEquilibrium:
    """Solve the same trade-cost counterfactual from baseline sufficient statistics."""

    hat = _as_float_array(trade_cost_hat, "trade_cost_hat")
    shape = (primitives.countries, primitives.countries)
    if hat.shape != shape or np.any(hat <= 0):
        raise ValueError("trade_cost_hat must be positive and match bilateral shares")
    primitives.with_trade_cost_hat(hat)  # Validate economically feasible counterfactual costs.
    if baseline.trade_shares.shape != shape:
        raise ValueError("baseline trade shares do not match primitives")

    def implied_objects(free_log_wage_hats: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        wage_hats = np.concatenate(([1.0], np.exp(free_log_wage_hats)))
        delivered_cost_hats = wage_hats[np.newaxis, :] * hat
        reweighting = delivered_cost_hats ** (-primitives.theta)
        denominator = np.sum(baseline.trade_shares * reweighting, axis=1)
        counterfactual_shares = baseline.trade_shares * reweighting / denominator[:, np.newaxis]
        price_hats = denominator ** (-1.0 / primitives.theta)
        return wage_hats, counterfactual_shares, price_hats

    def residual(free_log_wage_hats: np.ndarray) -> np.ndarray:
        wage_hats, counterfactual_shares, _ = implied_objects(free_log_wage_hats)
        counterfactual_income = wage_hats * baseline.income
        export_revenue = counterfactual_shares.T @ counterfactual_income
        imbalance = (counterfactual_income - export_revenue) / counterfactual_income
        return imbalance[1:]

    solution = least_squares(
        residual,
        x0=np.zeros(primitives.countries - 1),
        xtol=1e-14,
        ftol=1e-14,
        gtol=1e-14,
        max_nfev=max_evaluations,
    )
    wage_hats, counterfactual_shares, price_hats = implied_objects(solution.x)
    counterfactual_income = wage_hats * baseline.income
    full_residual = (
        counterfactual_income - counterfactual_shares.T @ counterfactual_income
    ) / counterfactual_income
    residual_norm = float(np.max(np.abs(full_residual)))
    diagnostics = SolverDiagnostics(
        converged=bool(solution.success and residual_norm <= residual_tolerance),
        residual_norm=residual_norm,
        evaluations=int(solution.nfev),
        message=str(solution.message),
    )
    return HatEquilibrium(
        wage_hats=wage_hats,
        counterfactual_trade_shares=counterfactual_shares,
        price_hats=price_hats,
        real_wage_hats=wage_hats / price_hats,
        diagnostics=diagnostics,
    )
