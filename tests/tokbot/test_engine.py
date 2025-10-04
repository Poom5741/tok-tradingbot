import pytest

from trading.engine import calc_amount_out


def test_calc_amount_out_uniswap_v2_math():
    # With equal reserves, amount_out is roughly amount_in minus fee impact
    amount_in = 1_000_000
    reserve_in = 100_000_000
    reserve_out = 100_000_000
    out = calc_amount_out(amount_in, reserve_in, reserve_out, fee_bps=25)
    assert out > 0
    assert out < amount_in