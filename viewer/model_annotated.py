"""Reader-oriented reconstruction for the one-industry EK viewer.

This is executable explanatory code, not the production source of truth.
The manifest maps these reader-oriented functions to their production modules.
"""

from __future__ import annotations

import numpy as np

from ek_model import compare_equivalence, solve_exact_hat, solve_full
from ek_model.model import Equilibrium, Primitives


# @step:full_trade_system
def derive_trade_shares_and_prices(primitives: Primitives, wages: np.ndarray):
    """Map candidate wages into bilateral shares and importer price indices."""
    # Rows n are importers; columns i are exporters.
    delivered_cost = wages[np.newaxis, :] * primitives.trade_costs
    competitiveness = primitives.technology[np.newaxis, :] * delivered_cost ** (-primitives.theta)
    denominator = competitiveness.sum(axis=1)
    trade_shares = competitiveness / denominator[:, np.newaxis]
    price_indices = primitives.price_constant * denominator ** (-1.0 / primitives.theta)
    return trade_shares, price_indices


# @step:full_residual
def build_levels_market_residual(
    primitives: Primitives,
    wages: np.ndarray,
    trade_shares: np.ndarray,
):
    """Compare each exporter's factor income with sales to all importers."""
    income = wages * primitives.labor
    export_revenue = trade_shares.T @ income
    return (income - export_revenue) / income


# @step:full_solver
def full_solution_route(primitives: Primitives) -> Equilibrium:
    """Production solver fixes wage[0]=1 and zeros the remaining residuals."""
    equilibrium = solve_full(primitives)
    if not equilibrium.diagnostics.converged:
        raise RuntimeError(equilibrium.diagnostics.message)
    return equilibrium


# @step:hat_inputs
def exact_hat_inputs(baseline: Equilibrium, trade_cost_hat: np.ndarray):
    """Only baseline income, baseline shares, and the exogenous shock are needed."""
    return baseline.income, baseline.trade_shares, trade_cost_hat


# @step:hat_shares_prices
def derive_hat_shares_and_prices(
    baseline_shares: np.ndarray,
    wage_hat: np.ndarray,
    trade_cost_hat: np.ndarray,
    theta: float,
):
    """Reweight baseline shares by counterfactual delivered-cost changes."""
    delivered_cost_hat = wage_hat[np.newaxis, :] * trade_cost_hat
    reweighting = delivered_cost_hat ** (-theta)
    denominator = np.sum(baseline_shares * reweighting, axis=1)
    counterfactual_shares = baseline_shares * reweighting / denominator[:, np.newaxis]
    price_hat = denominator ** (-1.0 / theta)
    return counterfactual_shares, price_hat


# @step:hat_residual
def build_hat_market_residual(
    baseline_income: np.ndarray,
    wage_hat: np.ndarray,
    counterfactual_shares: np.ndarray,
):
    """Clear counterfactual markets using baseline income as the scale."""
    counterfactual_income = wage_hat * baseline_income
    export_revenue = counterfactual_shares.T @ counterfactual_income
    return (counterfactual_income - export_revenue) / counterfactual_income


# @step:hat_solver
def exact_hat_route(primitives, baseline, trade_cost_hat):
    """Production solver fixes wage_hat[0]=1 and zeros the hat residuals."""
    hats = solve_exact_hat(primitives, baseline, trade_cost_hat)
    if not hats.diagnostics.converged:
        raise RuntimeError(hats.diagnostics.message)
    return hats


# @step:test_routes
def run_both_counterfactual_routes(primitives, trade_cost_hat):
    """Solve E0 and E1 in levels, then solve the same E1 from E0 in hats."""
    baseline = full_solution_route(primitives)
    counterfactual = full_solution_route(primitives.with_trade_cost_hat(trade_cost_hat))
    hats = exact_hat_route(primitives, baseline, trade_cost_hat)
    return baseline, counterfactual, hats


# @step:test_compare
def certify_equivalence(primitives, trade_cost_hat):
    """A passing certificate requires convergence and errors below tolerance."""
    baseline, counterfactual, hats = run_both_counterfactual_routes(primitives, trade_cost_hat)
    certificate = compare_equivalence(baseline, counterfactual, hats, tolerance=1e-9)
    if not certificate.passed:
        raise AssertionError(certificate.as_dict())
    return certificate
