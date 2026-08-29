import numpy as np
import pytest

from ek_model import (
    Primitives,
    compare_equivalence,
    example_primitives,
    example_trade_cost_hat,
    solve_exact_hat,
    solve_full,
)
from ek_model.model import wage_tatonnement_step


def test_two_full_solutions_equal_exact_hat_counterfactual() -> None:
    primitives = example_primitives()
    trade_cost_hat = example_trade_cost_hat()
    baseline = solve_full(primitives)
    counterfactual = solve_full(primitives.with_trade_cost_hat(trade_cost_hat))
    hats = solve_exact_hat(primitives, baseline, trade_cost_hat)
    certificate = compare_equivalence(baseline, counterfactual, hats)

    assert baseline.diagnostics.converged
    assert counterfactual.diagnostics.converged
    assert hats.diagnostics.converged
    assert baseline.diagnostics.iterations > 0
    assert counterfactual.diagnostics.iterations > 0
    assert hats.diagnostics.iterations > 0
    assert certificate.passed, certificate.as_dict()
    assert baseline.wages[0] == counterfactual.wages[0] == hats.wage_hats[0] == 1.0
    np.testing.assert_allclose(baseline.trade_shares.sum(axis=1), 1.0, atol=1e-14)
    np.testing.assert_allclose(counterfactual.trade_shares.sum(axis=1), 1.0, atol=1e-14)


def test_primitives_require_only_positive_trade_costs() -> None:
    with pytest.raises(ValueError, match="shape"):
        Primitives(np.ones(3), np.ones(3), np.ones((3, 2)), theta=4.0)
    unrestricted_positive_costs = np.array(
        [[0.5, 2.0, 1.0], [1.2, 3.0, 0.8], [4.0, 1.1, 0.25]]
    )
    accepted = Primitives(np.ones(3), np.ones(3), unrestricted_positive_costs, theta=4.0)
    assert np.array_equal(accepted.trade_costs, unrestricted_positive_costs)
    unrestricted_positive_hat = np.array(
        [[0.2, 1.1, 3.0], [4.0, 0.7, 2.0], [1.3, 0.6, 5.0]]
    )
    counterfactual = accepted.with_trade_cost_hat(unrestricted_positive_hat)
    np.testing.assert_allclose(
        counterfactual.trade_costs,
        unrestricted_positive_costs * unrestricted_positive_hat,
    )
    with pytest.raises(ValueError, match="strictly positive"):
        Primitives(np.ones(3), np.ones(3), np.zeros((3, 3)), theta=4.0)


def test_wage_iteration_moves_toward_sales_and_restores_numeraire() -> None:
    wages = np.ones(3)
    income = np.ones(3)
    shares = np.array(
        [[0.6, 0.3, 0.1], [0.6, 0.3, 0.1], [0.6, 0.3, 0.1]]
    )
    updated = wage_tatonnement_step(wages, income, shares, damping=0.25)

    assert updated[0] == 1.0
    assert updated[1] < 1.0
    assert updated[2] < updated[1]


def test_iteration_reports_nonconvergence_at_update_limit() -> None:
    result = solve_full(example_primitives(), max_iterations=1)
    assert not result.diagnostics.converged
    assert result.diagnostics.iterations == 1
    assert "without convergence" in result.diagnostics.message
