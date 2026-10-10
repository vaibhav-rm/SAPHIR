import sys
sys.path.insert(0, "src")
sys.path.insert(0, "evals")
from amortization import measure, rows, english_turn_cost


def test_handshake_and_turn_sizes_sane():
    hs, turns = measure()
    assert 500 <= hs <= 800, hs
    assert all(100 <= t <= 400 for t in turns), turns


def test_cost_breakeven_immediate_and_grows():
    hs, turns = measure()
    data = rows(hs, turns)
    assert data[0]["saphir_cost_usd"] < data[0]["eng_cost_usd"]
    ratio_20 = data[19]["eng_cost_usd"] / data[19]["saphir_cost_usd"]
    assert ratio_20 > 10, ratio_20


def test_english_baseline_positive():
    usd, sec = english_turn_cost()
    assert usd > 0 and sec > 0
