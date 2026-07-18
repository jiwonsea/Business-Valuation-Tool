import pytest

from engine.beta_regression import regress_beta


def test_regress_beta_recovers_ols_slope():
    benchmark = [((i % 9) - 4) / 100 for i in range(80)]
    stock = [0.003 + 1.75 * value for value in benchmark]

    beta, observations = regress_beta(stock, benchmark)

    assert observations == 80
    assert beta == pytest.approx(1.75)


def test_regress_beta_rejects_zero_benchmark_variance():
    with pytest.raises(ValueError, match="variance"):
        regress_beta([0.01, 0.02], [0.01, 0.01])
