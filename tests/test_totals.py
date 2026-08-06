"""The money math. Every number a client sees comes out of compute_totals."""
import doc_generator


def items(*pairs):
    return [{"qty": q, "rate": r} for q, r in pairs]


def test_subtotal_is_qty_times_rate_summed():
    totals = doc_generator.compute_totals(items((2, 100.0), (3, 50.0)))
    assert totals["subtotal"] == 350.0


def test_vat_is_five_percent_of_discounted_subtotal():
    totals = doc_generator.compute_totals(items((1, 1000.0)))
    assert totals["vat"] == 50.0
    assert totals["grand_total"] == 1050.0


def test_percent_discount_applies_before_vat():
    totals = doc_generator.compute_totals(items((1, 1000.0)), "percent", 10)
    assert totals["discount_amount"] == 100.0
    assert totals["discounted_subtotal"] == 900.0
    # VAT must be charged on what the client actually pays, not the pre-discount figure.
    assert totals["vat"] == 45.0
    assert totals["grand_total"] == 945.0


def test_flat_discount_applies_before_vat():
    totals = doc_generator.compute_totals(items((1, 1000.0)), "flat", 250)
    assert totals["discounted_subtotal"] == 750.0
    assert totals["grand_total"] == 787.5


def test_discount_cannot_exceed_subtotal():
    """A flat discount larger than the order must zero the total, never go negative."""
    totals = doc_generator.compute_totals(items((1, 100.0)), "flat", 500)
    assert totals["discount_amount"] == 100.0
    assert totals["grand_total"] == 0.0


def test_negative_discount_is_ignored():
    """A negative discount would otherwise silently inflate the price above list."""
    totals = doc_generator.compute_totals(items((1, 100.0)), "flat", -50)
    assert totals["discount_amount"] == 0.0
    assert totals["grand_total"] == 105.0


def test_unknown_discount_type_charges_full_price():
    totals = doc_generator.compute_totals(items((1, 200.0)), "bogus", 50)
    assert totals["discount_amount"] == 0.0
    assert totals["subtotal"] == 200.0


def test_missing_and_null_fields_do_not_crash():
    totals = doc_generator.compute_totals([{"qty": None, "rate": None}, {}, {"qty": 2}])
    assert totals["subtotal"] == 0.0
    assert totals["grand_total"] == 0.0


def test_empty_draft_totals_zero():
    assert doc_generator.compute_totals([])["grand_total"] == 0.0


def test_valid_until_adds_days():
    assert doc_generator.compute_valid_until("2026-01-01", 14) == "2026-01-15"


def test_valid_until_tolerates_unparseable_date():
    """Falls back to today rather than raising mid-compile and losing the quote."""
    assert len(doc_generator.compute_valid_until("not-a-date", 7)) == 10
