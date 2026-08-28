# Latest State: One-Industry Eaton–Kortum Model

This document is the Single Source of Truth for the reviewed model on this branch. The next PDCU cycle should generalize this implementation in place to multiple industries; it should not create a parallel one-industry solver.

## Economic environment

There are three countries in the verification fixture, indexed by importer `n` and exporter `i`. Each country has technology `T[i]` and labor `L[i]`. Labor is the only factor. Bilateral iceberg trade costs are stored as `d[n, i]`, with importer rows and exporter columns, and `d[n, n] = 1`.

The model has balanced trade and no intermediate inputs, tariffs, tariff revenue, transfers, or exogenous deficits.

Conditional on wages, importer `n`'s expenditure share on exporter `i` is

$$
\pi_{ni}=
\frac{T_i(w_i d_{ni})^{-\theta}}
{\sum_k T_k(w_k d_{nk})^{-\theta}}.
$$

The price index is

$$
P_n=\gamma
\left[\sum_iT_i(w_i d_{ni})^{-\theta}\right]^{-1/\theta}.
$$

Balanced-trade market clearing determines relative wages:

$$
w_iL_i=\sum_n\pi_{ni}w_nL_n.
$$

Country 0's wage is fixed at one. This condition is imposed exactly by excluding it from the numerical unknown vector. Market clearing is a convergence condition: the solver is accepted only when the maximum normalized residual across all countries is no more than `1e-11`.

## Solution routes

The full solver works in log wages for countries 1 through `N-1`. At each candidate it derives delivered costs, trade shares, price indices, factor income, and normalized market-clearing residuals.

For a trade-cost counterfactual with fixed technology and labor, the exact-hat solver uses baseline shares and incomes:

$$
\pi'_{ni}=
\frac{\pi_{ni}(\widehat w_i\widehat d_{ni})^{-\theta}}
{\sum_k\pi_{nk}(\widehat w_k\widehat d_{nk})^{-\theta}},
\qquad
\widehat P_n=
\left[\sum_i\pi_{ni}(\widehat w_i\widehat d_{ni})^{-\theta}\right]^{-1/\theta}.
$$

The hat solver fixes `wage_hat[0] = 1`, matching the normalization used in both full solutions.

## Verification certificate

The fixture uses heterogeneous technology, labor, and bilateral costs with `theta = 4`. The counterfactual reduces trade costs in both directions between countries 0 and 1 by 10 percent.

The acceptance test solves baseline `E0` and counterfactual `E1` in levels, solves the same counterfactual in exact hats from `E0`, and compares:

- wage changes;
- price-index changes;
- counterfactual bilateral trade shares; and
- real-wage changes.

Every solver must converge, and both the maximum absolute and maximum relative error for every object must be at most `1e-9`. The generated viewer reports the actual error and residual values; its current certificate passes with comparison errors on the order of `1e-15`.

## Educational artifacts

Run `uv run python scripts/build_model_viewer.py` to regenerate the standalone viewer and manifest from the production source, annotated explanatory reconstruction, quiz, and fresh numerical solutions. The annotated code is not production code; `viewer/manifest.json` records its mapping to production functions and hashes every production source file.

Run `uv run --extra test pytest` for the economic and artifact checks.
