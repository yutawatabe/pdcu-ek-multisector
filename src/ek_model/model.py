"""Data contracts and shared Eaton-Kortum algebra.

Every bilateral array uses ``[importer, exporter]`` order.  The explicit
contract is intentionally repeated in the viewer because reversing these two
axes is the most consequential indexing mistake in this small model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def _as_float_array(value: object, name: str) -> FloatArray:
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


@dataclass(frozen=True)
class Primitives:
    """One-industry primitives with ``trade_costs[importer, exporter]``."""

    technology: FloatArray
    labor: FloatArray
    trade_costs: FloatArray
    theta: float
    price_constant: float = 1.0

    def __post_init__(self) -> None:
        technology = _as_float_array(self.technology, "technology")
        labor = _as_float_array(self.labor, "labor")
        trade_costs = _as_float_array(self.trade_costs, "trade_costs")
        if technology.ndim != 1 or labor.ndim != 1:
            raise ValueError("technology and labor must be one-dimensional")
        if technology.shape != labor.shape:
            raise ValueError("technology and labor must have the same shape")
        countries = technology.size
        if countries < 2 or trade_costs.shape != (countries, countries):
            raise ValueError("trade_costs must have shape (countries, countries)")
        if np.any(technology <= 0) or np.any(labor <= 0):
            raise ValueError("technology and labor must be strictly positive")
        if np.any(trade_costs <= 0):
            raise ValueError("trade costs must be strictly positive")
        if not np.isfinite(self.theta) or self.theta <= 0:
            raise ValueError("theta must be strictly positive")
        if not np.isfinite(self.price_constant) or self.price_constant <= 0:
            raise ValueError("price_constant must be strictly positive")
        object.__setattr__(self, "technology", technology)
        object.__setattr__(self, "labor", labor)
        object.__setattr__(self, "trade_costs", trade_costs)

    @property
    def countries(self) -> int:
        return int(self.technology.size)

    def with_trade_cost_hat(self, trade_cost_hat: object) -> "Primitives":
        hat = _as_float_array(trade_cost_hat, "trade_cost_hat")
        if hat.shape != self.trade_costs.shape or np.any(hat <= 0):
            raise ValueError("trade_cost_hat must be positive and match trade_costs")
        new_costs = self.trade_costs * hat
        return Primitives(
            technology=self.technology,
            labor=self.labor,
            trade_costs=new_costs,
            theta=self.theta,
            price_constant=self.price_constant,
        )


@dataclass(frozen=True)
class SolverDiagnostics:
    converged: bool
    residual_norm: float
    iterations: int
    message: str


@dataclass(frozen=True)
class Equilibrium:
    wages: FloatArray
    trade_shares: FloatArray
    price_indices: FloatArray
    income: FloatArray
    real_wages: FloatArray
    diagnostics: SolverDiagnostics


@dataclass(frozen=True)
class HatEquilibrium:
    wage_hats: FloatArray
    counterfactual_trade_shares: FloatArray
    price_hats: FloatArray
    real_wage_hats: FloatArray
    diagnostics: SolverDiagnostics


def trade_system(primitives: Primitives, wages: object) -> tuple[FloatArray, FloatArray]:
    """Return trade shares and price indices at candidate wages."""

    wages_array = _as_float_array(wages, "wages")
    if wages_array.shape != (primitives.countries,) or np.any(wages_array <= 0):
        raise ValueError("wages must be positive with one entry per country")
    delivered_costs = wages_array[np.newaxis, :] * primitives.trade_costs
    competitiveness = primitives.technology[np.newaxis, :] * delivered_costs ** (-primitives.theta)
    denominator = competitiveness.sum(axis=1)
    trade_shares = competitiveness / denominator[:, np.newaxis]
    price_indices = primitives.price_constant * denominator ** (-1.0 / primitives.theta)
    return trade_shares, price_indices


def normalized_market_residual(
    labor: FloatArray,
    wages: FloatArray,
    trade_shares: FloatArray,
) -> FloatArray:
    """Return country market imbalances divided by own factor income."""

    income = wages * labor
    export_revenue = trade_shares.T @ income
    return (income - export_revenue) / income


def wage_tatonnement_step(
    wages: FloatArray,
    income: FloatArray,
    trade_shares: FloatArray,
    damping: float,
) -> FloatArray:
    """Raise wages where sales exceed income, then restore ``wage[0] == 1``.

    The multiplicative update preserves positivity.  Damping controls the
    fraction of the sales-to-income gap applied in each iteration.
    """

    export_revenue = trade_shares.T @ income
    sales_to_income = export_revenue / income
    provisional_wages = wages * sales_to_income**damping
    return provisional_wages / provisional_wages[0]


def example_primitives() -> Primitives:
    """Small heterogeneous fixture used throughout the PDCU certificate."""

    return Primitives(
        technology=np.array([1.00, 1.25, 0.82]),
        labor=np.array([1.00, 1.35, 0.78]),
        trade_costs=np.array(
            [
                [1.00, 1.32, 1.58],
                [1.36, 1.00, 1.44],
                [1.62, 1.47, 1.00],
            ]
        ),
        theta=4.0,
    )


def example_trade_cost_hat() -> FloatArray:
    """Symmetric ten-percent trade-cost cut between countries 0 and 1."""

    hat = np.ones((3, 3))
    hat[0, 1] = 0.9
    hat[1, 0] = 0.9
    return hat
