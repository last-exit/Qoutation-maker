"""Client identity, quote numbering and the ledger."""
import pytest


def quote(client="Acme360", phone="", total=1000.0, **kw):
    payload = {
        "client_name": client, "client_phone": phone, "venue": "Kite Beach",
        "quote_date": "2026-08-01", "items": [{"description": "Pirate Ship", "qty": 1, "rate": total}],
        "subtotal": total, "vat": 0, "grand_total": total,
    }
    payload.update(kw)
    return payload


# --- Client identity ------------------------------------------------------------------

@pytest.mark.parametrize("written", ["Acme360", "acme 360", "Acme360 L.L.C.", "  Acme360  "])
def test_name_variants_normalize_to_one_identity(written):
    import history_db
    assert history_db.normalize_client_name(written) == "acme360"


def test_distinct_companies_stay_distinct():
    import history_db
    assert history_db.normalize_client_name("Red Cube") != history_db.normalize_client_name("Blue Cube")


def test_phone_variants_normalize():
    import history_db
    forms = ["+971 50 123 4567", "0501234567", "00971501234567", "971-50-123-4567"]
    assert len({history_db.normalize_phone(f) for f in forms}) == 1


def test_quotes_typed_differently_land_on_one_client(temp_history):
    """The reason the ledger existed but produced wrong numbers."""
    temp_history.save_quotation_history(quote(client="Acme360", total=1000))
    temp_history.save_quotation_history(quote(client="Acme 360 LLC", total=500))

    clients = temp_history.get_clients()
    assert len(clients) == 1
    assert clients[0]["quote_count"] == 2


def test_ledger_totals_only_count_won_quotes(temp_history):
    a = temp_history.save_quotation_history(quote(total=1000))
    b = temp_history.save_quotation_history(quote(total=500))
    temp_history.update_quotation_status(a, "Won")
    temp_history.update_quotation_status(b, "Lost")
    temp_history.update_payment(a, "Partial", 400)

    ledger = temp_history.get_client_ledger("Acme360")
    assert ledger["total_billed"] == 1000.0
    assert ledger["total_paid"] == 400.0
    assert ledger["total_outstanding"] == 600.0


def test_ledger_for_unknown_client_is_empty_not_an_error(temp_history):
    ledger = temp_history.get_client_ledger("Nobody At All")
    assert ledger["items"] == []
    assert ledger["total_outstanding"] == 0.0


def test_merge_moves_quotes_and_redirects_future_ones(temp_history):
    temp_history.save_quotation_history(quote(client="Red Cube", phone="0501111111", total=100))
    temp_history.save_quotation_history(quote(client="Red Cube", phone="0509999999", total=200))
    clients = {c["phone"]: c["id"] for c in temp_history.get_clients()}
    assert len(clients) == 2, "different phones legitimately hold them apart until merged"

    moved = temp_history.merge_clients(clients["0509999999"], clients["0501111111"])
    assert moved == 1

    remaining = temp_history.get_clients()
    assert len(remaining) == 1
    assert remaining[0]["quote_count"] == 2


def test_merge_into_self_is_rejected(temp_history):
    temp_history.save_quotation_history(quote())
    cid = temp_history.get_clients()[0]["id"]
    with pytest.raises(ValueError):
        temp_history.merge_clients(cid, cid)


def test_duplicate_finder_surfaces_split_identities(temp_history):
    temp_history.save_quotation_history(quote(client="Red Cube", phone="0501111111"))
    temp_history.save_quotation_history(quote(client="Red Cube", phone="0509999999"))
    groups = temp_history.find_duplicate_clients()
    assert len(groups) == 1
    assert len(groups[0]["clients"]) == 2


# --- Quote numbering ------------------------------------------------------------------

def test_numbers_are_sequential(temp_history):
    assert [temp_history.allocate_quote_number() for _ in range(3)] == ["Q-1", "Q-2", "Q-3"]


def test_deleting_the_last_quote_does_not_recycle_its_number(temp_history):
    """The old MAX(id)+1 scheme put two different documents in a client's inbox as Q-7."""
    first = temp_history.allocate_quote_number()
    qid = temp_history.save_quotation_history(quote(quote_number=first))
    temp_history.delete_quotation_history(qid)

    assert temp_history.allocate_quote_number() != first


def test_peek_does_not_consume(temp_history):
    peeked = temp_history.peek_quote_number()
    assert temp_history.peek_quote_number() == peeked
    assert temp_history.allocate_quote_number() == peeked


def test_concurrent_allocation_never_collides(temp_history):
    """pywebview dispatches each JS call on its own thread, so two compiles can overlap."""
    import threading

    seen, lock = [], threading.Lock()

    def grab():
        number = temp_history.allocate_quote_number()
        with lock:
            seen.append(number)

    threads = [threading.Thread(target=grab) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(seen)) == 12


# --- Margin ---------------------------------------------------------------------------

def test_margin_counts_only_lines_with_a_captured_cost(temp_history):
    qid = temp_history.save_quotation_history({
        **quote(total=1000),
        "items": [
            {"description": "Pirate Ship", "qty": 2, "rate": 100.0, "cost_price": 60.0},
            {"description": "Delivery", "qty": 1, "rate": 50.0, "cost_price": None},
        ],
    })
    temp_history.update_quotation_status(qid, "Won")

    summary = temp_history.get_margin_summary(period_days=3650)
    assert summary["total_margin"] == 80.0
    assert summary["items_with_cost"] == 1
    assert summary["items_without_cost"] == 1


def test_margin_ignores_quotes_that_were_not_won(temp_history):
    temp_history.save_quotation_history({
        **quote(),
        "items": [{"description": "X", "qty": 1, "rate": 100.0, "cost_price": 10.0}],
    })
    assert temp_history.get_margin_summary(period_days=3650)["items_with_cost"] == 0


# --- History listing ------------------------------------------------------------------

def test_history_list_omits_line_items_by_default(temp_history):
    """The list only renders client, date and total; deserializing every line item of 200
    quotes to show that was the most expensive call in the app."""
    temp_history.save_quotation_history(quote())
    rows = temp_history.get_quotation_history()
    assert "items" not in rows[0]
    assert "items" in temp_history.get_quotation_history(include_items=True)[0]


def test_image_refs_are_collected_for_orphan_protection(temp_history):
    temp_history.save_quotation_history({
        **quote(),
        "items": [{"description": "X", "qty": 1, "rate": 1.0, "image_ref": "a" * 64}],
    })
    assert "a" * 64 in temp_history.all_image_refs()


def test_invalid_status_is_rejected(temp_history):
    qid = temp_history.save_quotation_history(quote())
    with pytest.raises(ValueError):
        temp_history.update_quotation_status(qid, "Maybe")
