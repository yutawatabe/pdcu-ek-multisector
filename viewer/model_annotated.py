"""Reader-oriented reconstruction of the wage-iteration solvers.

This file is executable explanatory code, not the production source of truth.
The manifest maps every reader function below to reviewed production code.
"""

from __future__ import annotations

import numpy as np

from ek_model import compare_equivalence, solve_exact_hat, solve_full
from ek_model.model import Equilibrium, Primitives


# @step:full_init
def initialize_level_wages(number_of_countries: int) -> np.ndarray:
    """Use equal positive wages as the first guess and choose country 0 as numeraire."""
    wages = np.ones(number_of_countries)
    wages = wages / wages[0]
    return wages


# @step:full_trade
def derive_level_trade_objects(primitives: Primitives, wages: np.ndarray):
    """Given wages, compute delivered costs, importer shares, and price indices."""
    # Every row n is an importer; every column i is an exporter.
    delivered_cost = wages[np.newaxis, :] * primitives.trade_costs
    competitiveness = primitives.technology[np.newaxis, :] * delivered_cost ** (-primitives.theta)
    denominator = competitiveness.sum(axis=1)
    trade_shares = competitiveness / denominator[:, np.newaxis]
    price_indices = primitives.price_constant * denominator ** (-1.0 / primitives.theta)
    return trade_shares, price_indices


# @step:full_sales
def measure_level_market_imbalance(
    primitives: Primitives,
    wages: np.ndarray,
    trade_shares: np.ndarray,
):
    """Compare each exporter's sales to its wage bill."""
    income = wages * primitives.labor
    export_revenue = trade_shares.T @ income
    residual = (income - export_revenue) / income
    return income, export_revenue, residual


# @step:full_update
def update_and_normalize_wages(
    wages: np.ndarray,
    income: np.ndarray,
    export_revenue: np.ndarray,
    damping: float,
):
    """Raise a wage when sales exceed income, damp the move, and restore the numeraire."""
    sales_to_income = export_revenue / income
    provisional_wages = wages * sales_to_income**damping
    next_wages = provisional_wages / provisional_wages[0]
    return next_wages


# @step:full_solver
def solve_levels_by_wage_iteration(
    primitives: Primitives,
    tolerance: float = 1e-11,
    damping: float = 0.25,
    max_iterations: int = 10_000,
):
    """Repeat the economic wage map until every market clears."""
    wages = initialize_level_wages(primitives.countries)
    for iteration in range(max_iterations + 1):
        trade_shares, price_indices = derive_level_trade_objects(primitives, wages)
        income, export_revenue, residual = measure_level_market_imbalance(
            primitives, wages, trade_shares
        )
        if np.max(np.abs(residual)) <= tolerance:
            return {
                "wages": wages,
                "trade_shares": trade_shares,
                "price_indices": price_indices,
                "real_wages": wages / price_indices,
                "residual": residual,
                "iterations": iteration,
            }
        wages = update_and_normalize_wages(wages, income, export_revenue, damping)
    raise RuntimeError("wage iteration did not clear every market")


# @step:hat_init
def initialize_exact_hat_inputs(baseline: Equilibrium, trade_cost_hat: np.ndarray):
    """Hold baseline shares and income fixed; begin from no wage change."""
    wage_hats = np.ones_like(baseline.wages)
    return baseline.trade_shares, baseline.income, trade_cost_hat, wage_hats


# @step:hat_trade
def derive_hat_trade_objects(
    baseline_shares: np.ndarray,
    wage_hats: np.ndarray,
    trade_cost_hat: np.ndarray,
    theta: float,
):
    """Reweight baseline shares by delivered-cost hats."""
    delivered_cost_hat = wage_hats[np.newaxis, :] * trade_cost_hat
    reweighting = delivered_cost_hat ** (-theta)
    denominator = np.sum(baseline_shares * reweighting, axis=1)
    counterfactual_shares = baseline_shares * reweighting / denominator[:, np.newaxis]
    price_hats = denominator ** (-1.0 / theta)
    return counterfactual_shares, price_hats


# @step:hat_sales
def measure_hat_market_imbalance(
    baseline_income: np.ndarray,
    wage_hats: np.ndarray,
    counterfactual_shares: np.ndarray,
):
    """Compare counterfactual exporter sales with counterfactual income."""
    counterfactual_income = wage_hats * baseline_income
    export_revenue = counterfactual_shares.T @ counterfactual_income
    residual = (counterfactual_income - export_revenue) / counterfactual_income
    return counterfactual_income, export_revenue, residual


# @step:hat_update
def update_and_normalize_wage_hats(
    wage_hats: np.ndarray,
    counterfactual_income: np.ndarray,
    export_revenue: np.ndarray,
    damping: float,
):
    """Apply the same multiplicative wage map in changes."""
    sales_to_income = export_revenue / counterfactual_income
    provisional_hats = wage_hats * sales_to_income**damping
    next_wage_hats = provisional_hats / provisional_hats[0]
    return next_wage_hats


# @step:hat_solver
def solve_hats_by_wage_iteration(
    primitives: Primitives,
    baseline: Equilibrium,
    trade_cost_hat: np.ndarray,
    tolerance: float = 1e-11,
    damping: float = 0.25,
    max_iterations: int = 10_000,
):
    """Repeat the hat wage map until every counterfactual market clears."""
    shares0, income0, trade_cost_hat, wage_hats = initialize_exact_hat_inputs(
        baseline, trade_cost_hat
    )
    for iteration in range(max_iterations + 1):
        shares1, price_hats = derive_hat_trade_objects(
            shares0, wage_hats, trade_cost_hat, primitives.theta
        )
        income1, export_revenue, residual = measure_hat_market_imbalance(
            income0, wage_hats, shares1
        )
        if np.max(np.abs(residual)) <= tolerance:
            return {
                "wage_hats": wage_hats,
                "counterfactual_shares": shares1,
                "price_hats": price_hats,
                "real_wage_hats": wage_hats / price_hats,
                "residual": residual,
                "iterations": iteration,
            }
        wage_hats = update_and_normalize_wage_hats(
            wage_hats, income1, export_revenue, damping
        )
    raise RuntimeError("wage-hat iteration did not clear every market")


# @step:test_routes
def run_both_counterfactual_routes(primitives, trade_cost_hat):
    """Solve E0 and E1 in levels, then solve the same E1 from E0 in hats."""
    baseline = solve_full(primitives)
    counterfactual = solve_full(primitives.with_trade_cost_hat(trade_cost_hat))
    hats = solve_exact_hat(primitives, baseline, trade_cost_hat)
    return baseline, counterfactual, hats


# @step:test_compare
def certify_equivalence(primitives, trade_cost_hat):
    """Require solver convergence and errors below the pre-specified tolerance."""
    baseline, counterfactual, hats = run_both_counterfactual_routes(
        primitives, trade_cost_hat
    )
    certificate = compare_equivalence(
        baseline, counterfactual, hats, tolerance=1e-9
    )
    if not certificate.passed:
        raise AssertionError(certificate.as_dict())
    return certificate
