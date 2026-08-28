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
    assert certificate.passed, certificate.as_dict()
    assert baseline.wages[0] == counterfactual.wages[0] == hats.wage_hats[0] == 1.0
    np.testing.assert_allclose(baseline.trade_shares.sum(axis=1), 1.0, atol=1e-14)
    np.testing.assert_allclose(counterfactual.trade_shares.sum(axis=1), 1.0, atol=1e-14)


def test_primitives_reject_reversed_or_economically_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="shape"):
        Primitives(np.ones(3), np.ones(3), np.ones((3, 2)), theta=4.0)
    bad_diagonal = np.ones((3, 3))
    bad_diagonal[0, 0] = 1.1
    with pytest.raises(ValueError, match="domestic"):
        Primitives(np.ones(3), np.ones(3), bad_diagonal, theta=4.0)
