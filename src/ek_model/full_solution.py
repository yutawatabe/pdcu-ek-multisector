"""Full levels solution for the one-industry Eaton-Kortum model."""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

from .model import Equilibrium, Primitives, SolverDiagnostics, normalized_market_residual, trade_system


def solve_full(
    primitives: Primitives,
    *,
    residual_tolerance: float = 1e-11,
    max_evaluations: int = 2_000,
) -> Equilibrium:
    """Solve relative wages with ``wage[0] == 1`` imposed exactly.

    The optimizer sees log wages for countries 1..N-1.  Market clearing for
    those countries is the independent residual system; the omitted country-0
    equation is checked again after solving and included in the certificate.
    """

    def residual(free_log_wages: np.ndarray) -> np.ndarray:
        wages = np.concatenate(([1.0], np.exp(free_log_wages)))
        trade_shares, _ = trade_system(primitives, wages)
        return normalized_market_residual(primitives.labor, wages, trade_shares)[1:]

    solution = least_squares(
        residual,
        x0=np.zeros(primitives.countries - 1),
        xtol=1e-14,
        ftol=1e-14,
        gtol=1e-14,
        max_nfev=max_evaluations,
    )
    wages = np.concatenate(([1.0], np.exp(solution.x)))
    trade_shares, price_indices = trade_system(primitives, wages)
    income = wages * primitives.labor
    full_residual = normalized_market_residual(primitives.labor, wages, trade_shares)
    residual_norm = float(np.max(np.abs(full_residual)))
    diagnostics = SolverDiagnostics(
        converged=bool(solution.success and residual_norm <= residual_tolerance),
        residual_norm=residual_norm,
        evaluations=int(solution.nfev),
        message=str(solution.message),
    )
    return Equilibrium(
        wages=wages,
        trade_shares=trade_shares,
        price_indices=price_indices,
        income=income,
        real_wages=wages / price_indices,
        diagnostics=diagnostics,
    )
