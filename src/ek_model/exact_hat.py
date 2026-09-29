"""Exact-hat counterfactual solution using baseline equilibrium shares."""

from __future__ import annotations

import numpy as np

from .model import (
    Equilibrium,
    HatEquilibrium,
    Primitives,
    SolverDiagnostics,
    _as_float_array,
    wage_tatonnement_step,
)


def solve_exact_hat(
    primitives: Primitives,
    baseline: Equilibrium,
    trade_cost_hat: object,
    *,
    residual_tolerance: float = 1e-11,
    damping: float = 0.25,
    max_iterations: int = 10_000,
) -> HatEquilibrium:
    """Solve the counterfactual by iterating on wage hats."""

    hat = _as_float_array(trade_cost_hat, "trade_cost_hat")
    shape = (primitives.countries, primitives.countries)
    if hat.shape != shape or np.any(hat <= 0):
        raise ValueError("trade_cost_hat must be positive and match bilateral shares")
    primitives.with_trade_cost_hat(hat)  # Validate only shape, finiteness, and positivity.
    if baseline.trade_shares.shape != shape:
        raise ValueError("baseline trade shares do not match primitives")
    if residual_tolerance <= 0:
        raise ValueError("residual_tolerance must be strictly positive")
    if not 0 < damping <= 1:
        raise ValueError("damping must lie in (0, 1]")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")

    def implied_objects(wage_hats: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        delivered_cost_hats = wage_hats[np.newaxis, :] * hat
        reweighting = delivered_cost_hats ** (-primitives.theta)
        denominator = np.sum(baseline.trade_shares * reweighting, axis=1)
        counterfactual_shares = baseline.trade_shares * reweighting / denominator[:, np.newaxis]
        price_hats = denominator ** (-1.0 / primitives.theta)
        return counterfactual_shares, price_hats

    wage_hats = np.ones(primitives.countries)
    converged = False
    residual_norm = float("inf")
    iterations = 0
    for iteration in range(max_iterations + 1):
        counterfactual_shares, price_hats = implied_objects(wage_hats)
        counterfactual_income = wage_hats * baseline.income
        export_revenue = counterfactual_shares.T @ counterfactual_income
        full_residual = (counterfactual_income - export_revenue) / counterfactual_income
        residual_norm = float(np.max(np.abs(full_residual)))
        if residual_norm <= residual_tolerance:
            converged = True
            iterations = iteration
            break
        if iteration == max_iterations:
            iterations = iteration
            break
        wage_hats = wage_tatonnement_step(
            wage_hats,
            counterfactual_income,
            counterfactual_shares,
            damping,
        )

    diagnostics = SolverDiagnostics(
        converged=converged,
        residual_norm=residual_norm,
        iterations=iterations,
        message=(
            "wage-hat iteration converged"
            if converged
            else f"wage-hat iteration reached {max_iterations} updates without convergence"
        ),
    )
    return HatEquilibrium(
        wage_hats=wage_hats,
        counterfactual_trade_shares=counterfactual_shares,
        price_hats=price_hats,
        real_wage_hats=wage_hats / price_hats,
        diagnostics=diagnostics,
    )
