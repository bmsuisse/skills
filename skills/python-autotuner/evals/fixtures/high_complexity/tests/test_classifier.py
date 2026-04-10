"""Tests for classifier.py."""
from classifier import classify_order, apply_pricing


def test_classify_invalid():
    assert classify_order(None) == "invalid"
    assert classify_order({}) == "invalid"
    assert classify_order({"amount": 100}) == "invalid"


def test_classify_premium_large_rush_EU():
    order = {"amount": 15000, "customer_type": "premium", "region": "EU", "is_rush": True, "payment_method": "wire"}
    assert classify_order(order) == "premium-large-rush-EU-wire"


def test_classify_premium_medium():
    order = {"amount": 5000, "customer_type": "premium"}
    assert classify_order(order) == "premium-medium"


def test_classify_standard_large_rush_discount():
    order = {"amount": 6000, "customer_type": "standard", "is_rush": True, "has_discount": True}
    assert classify_order(order) == "standard-large-rush-discount"


def test_classify_trial_overlimit():
    order = {"amount": 200, "customer_type": "trial"}
    assert classify_order(order) == "trial-overlimit"


def test_apply_pricing_premium_EU_rush():
    order = {"customer_type": "premium", "region": "EU", "is_rush": True, "amount": 500}
    price = apply_pricing(order, 100.0)
    # 100 * 0.85 * 1.20 + 25 + 10 = 102 + 35 = 137
    assert price == 137.0


def test_apply_pricing_none():
    assert apply_pricing(None, 100) == 0.0
    assert apply_pricing({}, 0) == 0.0


def test_apply_pricing_trial():
    order = {"customer_type": "trial", "region": "US"}
    assert apply_pricing(order, 100.0) == 110.0
