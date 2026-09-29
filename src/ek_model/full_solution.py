"""Full levels solution for the one-industry Eaton-Kortum model."""

from __future__ import annotations

import numpy as np

from .model import (
    Equilibrium,
    Primitives,
    SolverDiagnostics,
    normalized_market_residual,
    trade_system,
    wage_tatonnement_step,
)


def solve_full(
    primitives: Primitives,
    *,
    residual_tolerance: float = 1e-11,
    damping: float = 0.25,
    max_iterations: int = 10_000,
) -> Equilibrium:
    """Solve relative wages by damped multiplicative wage iteration.

    At each iteration an exporter whose sales exceed factor income receives a
    wage increase.  All wages are then divided by country 0's wage, imposing
    ``wage[0] == 1`` exactly without changing real allocations.
    """

    if residual_tolerance <= 0:
        raise ValueError("residual_tolerance must be strictly positive")
    if not 0 < damping <= 1:
        raise ValueError("damping must lie in (0, 1]")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")

    wages = np.ones(primitives.countries)
    converged = False
    residual_norm = float("inf")
    iterations = 0
    for iteration in range(max_iterations + 1):
        trade_shares, _ = trade_system(primitives, wages)
        full_residual = normalized_market_residual(primitives.labor, wages, trade_shares)
        residual_norm = float(np.max(np.abs(full_residual)))
        if residual_norm <= residual_tolerance:
            converged = True
            iterations = iteration
            break
        if iteration == max_iterations:
            iterations = iteration
            break
        income = wages * primitives.labor
        wages = wage_tatonnement_step(wages, income, trade_shares, damping)

    trade_shares, price_indices = trade_system(primitives, wages)
    income = wages * primitives.labor
    diagnostics = SolverDiagnostics(
        converged=converged,
        residual_norm=residual_norm,
        iterations=iterations,
        message=(
            "wage iteration converged"
            if converged
            else f"wage iteration reached {max_iterations} updates without convergence"
        ),
    )
    return Equilibrium(
        wages=wages,
        trade_shares=trade_shares,
        price_indices=price_indices,
        income=income,
        real_wages=wages / price_indices,
        diagnostics=diagnostics,
    )
