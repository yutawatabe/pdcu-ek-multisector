# Latest State: One-Industry Eaton–Kortum Model

This document is the Single Source of Truth for the reviewed model on this branch. The next PDCU cycle should generalize this implementation in place to multiple industries; it should not create a parallel one-industry solver.

## Economic environment

There are three countries in the verification fixture, indexed by importer `n` and exporter `i`. Each country has technology `T[i]` and labor `L[i]`. Labor is the only factor. Bilateral trade costs are stored as `d[n, i]`, with importer rows and exporter columns. The implementation requires only that every trade cost be finite and strictly positive; it imposes neither `d[n, i] >= 1` nor `d[n, n] = 1`.

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

Country 0's wage is fixed at one by renormalizing every wage iterate. Market clearing is a convergence condition: the solver is accepted only when the maximum normalized residual across all countries is no more than `1e-11`.

## Solution routes

The full solver uses damped multiplicative iteration on wages. Starting from $w_i^{(0)}=1$, iteration $k$ computes factor income and exporter sales,

$$
Y_i^{(k)}=w_i^{(k)}L_i,
\qquad
R_i^{(k)}=\sum_n\pi_{ni}^{(k)}Y_n^{(k)},
$$

and the normalized market-clearing residual

$$
F_i^{(k)}=\frac{Y_i^{(k)}-R_i^{(k)}}{Y_i^{(k)}}.
$$

If the maximum absolute residual exceeds the tolerance, wages are updated by

$$
w_i^{(k+1,\star)}
\leftarrow
w_i^{(k)}
\left(\frac{R_i^{(k)}}{Y_i^{(k)}}\right)^{\lambda},
\qquad \lambda=0.25,
$$

then renormalized:

$$
w_i^{(k+1)}
\leftarrow
\frac{w_i^{(k+1,\star)}}{w_0^{(k+1,\star)}}.
$$

Thus sales above income raise an exporter's wage, making its goods more expensive and increasing its factor income; sales below income lower its wage. Trade shares, prices, incomes, sales, and residuals are recomputed after every update. The solver returns only when $\max_i|F_i^{(k)}|\le 10^{-11}$, and reports failure after 10,000 updates.

For a trade-cost counterfactual with fixed technology and labor, the exact-hat solver uses baseline shares and incomes:

$$
\pi'_{ni}=
\frac{\pi_{ni}(\widehat w_i\widehat d_{ni})^{-\theta}}
{\sum_k\pi_{nk}(\widehat w_k\widehat d_{nk})^{-\theta}},
\qquad
\widehat P_n=
\left[\sum_i\pi_{ni}(\widehat w_i\widehat d_{ni})^{-\theta}\right]^{-1/\theta}.
$$

The hat solver starts from `wage_hat = 1` and applies the same damped sales-to-income update to wage hats. It renormalizes `wage_hat[0] = 1` after every update, matching the normalization used in both full solutions.

## Verification certificate

The fixture uses heterogeneous technology, labor, and bilateral costs with `theta = 4`. The counterfactual reduces trade costs in both directions between countries 0 and 1 by 10 percent.

The acceptance test solves baseline `E0` and counterfactual `E1` in levels, solves the same counterfactual in exact hats from `E0`, and compares:

- wage changes;
- price-index changes;
- counterfactual bilateral trade shares; and
- real-wage changes.

Every solver must converge, and both the maximum absolute and maximum relative error for every object must be at most `1e-9`. The generated viewer reports the actual error, wage-update count, and residual values. With the `1e-11` stopping rule, its current certificate passes with comparison errors on the order of `1e-12`.

## Educational artifacts

Run `uv run python scripts/build_model_viewer.py` to regenerate the standalone viewer and manifest from the production source, annotated explanatory reconstruction, quiz, and fresh numerical solutions. The annotated code is not production code; `viewer/manifest.json` records its mapping to production functions and hashes every production source file.

Run `uv run --extra test pytest` for the economic and artifact checks.
