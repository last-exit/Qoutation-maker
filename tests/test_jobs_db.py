"""Jobs, costs and suppliers — the money side of what happens after a quote is won."""
import pytest


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    import jobs_db
    monkeypatch.setattr(jobs_db, "DB_FILE", str(tmp_path / "jobs.db"))
    jobs_db.init_db()
    return jobs_db


# --- Job numbering ---------------------------------------------------------------------

def test_job_numbers_are_sequential_and_never_reused(jobs):
    """A job reference ends up on supplier paperwork and delivery notes. Two jobs sharing one
    is far worse than a gap."""
    first = jobs.create_job(client_name="Acme", quoted_total=1000)
    number = jobs.get_job(first)["job_number"]
    jobs.delete_job(first)

    second = jobs.create_job(client_name="Acme", quoted_total=1000)
    assert jobs.get_job(second)["job_number"] != number


def test_job_numbers_are_unique_under_concurrency(jobs):
    import threading
    seen, lock = [], threading.Lock()

    def grab():
        number = jobs.allocate_job_number()
        with lock:
            seen.append(number)

    threads = [threading.Thread(target=grab) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(seen)) == 10


# --- Jobs ------------------------------------------------------------------------------

def test_one_job_per_quotation(jobs):
    """Booking the same work twice would double-count both revenue and costs."""
    first = jobs.create_job(quotation_id=7, client_name="Acme", quoted_total=5000)
    again = jobs.create_job(quotation_id=7, client_name="Acme", quoted_total=5000)
    assert first == again
    assert len(jobs.get_jobs()) == 1


def test_job_without_a_quotation_is_allowed(jobs):
    """Not every job starts as a quotation — some are booked straight in."""
    a = jobs.create_job(client_name="Walk-in", quoted_total=100)
    b = jobs.create_job(client_name="Another", quoted_total=200)
    assert a != b
    assert len(jobs.get_jobs()) == 2


def test_lookup_by_quotation(jobs):
    jobs.create_job(quotation_id=9, client_name="Acme", quoted_total=5000)
    assert jobs.get_job_for_quotation(9)["client_name"] == "Acme"
    assert jobs.get_job_for_quotation(999) is None


def test_invalid_status_is_rejected(jobs):
    job_id = jobs.create_job(client_name="Acme")
    with pytest.raises(ValueError):
        jobs.update_job(job_id, status="Nearly Done")


def test_status_can_be_moved_through_the_lifecycle(jobs):
    job_id = jobs.create_job(client_name="Acme")
    for status in ("In Progress", "Complete"):
        jobs.update_job(job_id, status=status)
        assert jobs.get_job(job_id)["status"] == status


# --- Costs -----------------------------------------------------------------------------

def test_costs_roll_up_into_a_measured_margin(jobs):
    job_id = jobs.create_job(client_name="Acme", quoted_total=20000)
    jobs.add_job_cost(job_id, "Timber and hardware", category="Material", amount=11000)
    jobs.add_job_cost(job_id, "Install crew, 3 days", category="Labour", amount=2400)

    job = jobs.get_job(job_id)
    assert job["actual_cost"] == 13400.0
    assert job["margin"] == 6600.0
    assert job["margin_pct"] == 33.0
    assert job["has_costs"] is True


def test_a_job_with_no_costs_says_so(jobs):
    """A quoted margin presented as a measured one is how a business finds out it lost money
    after the fact."""
    job_id = jobs.create_job(client_name="Acme", quoted_total=20000)
    job = jobs.get_job(job_id)
    assert job["has_costs"] is False
    assert job["actual_cost"] == 0.0


def test_amount_defaults_to_quantity_times_unit_cost(jobs):
    job_id = jobs.create_job(client_name="Acme")
    jobs.add_job_cost(job_id, "Pine posts", quantity=12, unit_cost=45.5)
    assert jobs.get_job(job_id)["actual_cost"] == 546.0


def test_explicit_amount_wins_over_the_calculation(jobs):
    """Real invoices carry rounding, delivery and part-quantities that qty x unit does not
    reproduce."""
    job_id = jobs.create_job(client_name="Acme")
    jobs.add_job_cost(job_id, "Timber delivery", quantity=12, unit_cost=45.5, amount=560.25)
    assert jobs.get_job(job_id)["actual_cost"] == 560.25


def test_invalid_category_is_rejected(jobs):
    job_id = jobs.create_job(client_name="Acme")
    with pytest.raises(ValueError):
        jobs.add_job_cost(job_id, "Something", category="Vibes")


def test_cost_needs_a_description(jobs):
    job_id = jobs.create_job(client_name="Acme")
    with pytest.raises(ValueError):
        jobs.add_job_cost(job_id, "   ")


def test_breakdown_groups_spend_by_category(jobs):
    job_id = jobs.create_job(client_name="Acme", quoted_total=20000)
    jobs.add_job_cost(job_id, "Timber", category="Material", amount=8000)
    jobs.add_job_cost(job_id, "Fixings", category="Material", amount=1000)
    jobs.add_job_cost(job_id, "Crew", category="Labour", amount=2400)

    breakdown = {row["category"]: row["total"] for row in jobs.cost_breakdown(job_id)}
    assert breakdown == {"Material": 9000.0, "Labour": 2400.0}


def test_deleting_a_job_removes_its_costs(jobs):
    job_id = jobs.create_job(client_name="Acme")
    jobs.add_job_cost(job_id, "Timber", amount=100)
    jobs.delete_job(job_id)
    assert jobs.get_job_costs(job_id) == []


def test_costs_can_be_edited_and_removed(jobs):
    job_id = jobs.create_job(client_name="Acme", quoted_total=1000)
    cost_id = jobs.add_job_cost(job_id, "Timber", amount=400)
    jobs.update_job_cost(cost_id, amount=450)
    assert jobs.get_job(job_id)["actual_cost"] == 450.0
    jobs.delete_job_cost(cost_id)
    assert jobs.get_job(job_id)["actual_cost"] == 0.0


# --- Suppliers -------------------------------------------------------------------------

def test_supplier_name_variants_resolve_to_one_record(jobs):
    job_id = jobs.create_job(client_name="Acme")
    jobs.add_job_cost(job_id, "Timber", supplier_name="Al Noor Timber", amount=500)
    jobs.add_job_cost(job_id, "More timber", supplier_name="Al  Noor  Timber!", amount=300)

    suppliers = jobs.get_suppliers()
    assert len(suppliers) == 1
    assert suppliers[0]["total_spend"] == 800.0
    assert suppliers[0]["cost_entries"] == 2


def test_supplier_spend_is_what_makes_the_list_worth_keeping(jobs):
    job_id = jobs.create_job(client_name="Acme")
    jobs.add_job_cost(job_id, "Timber", supplier_name="Big Supplier", amount=9000)
    jobs.add_job_cost(job_id, "Screws", supplier_name="Small Supplier", amount=120)

    names = [s["name"] for s in jobs.get_suppliers()]
    assert names[0] == "Big Supplier", "highest spend should sort first"


def test_deleting_a_supplier_keeps_the_money_that_was_spent(jobs):
    """Costs are facts about money. Tidying a supplier record must not change any margin."""
    job_id = jobs.create_job(client_name="Acme", quoted_total=5000)
    jobs.add_job_cost(job_id, "Timber", supplier_name="Al Noor Timber", amount=800)
    supplier_id = jobs.get_suppliers()[0]["id"]

    jobs.delete_supplier(supplier_id)

    assert jobs.get_job(job_id)["actual_cost"] == 800.0
    assert jobs.get_job_costs(job_id)[0]["supplier_name"] is None


# --- Reporting -------------------------------------------------------------------------

def test_margin_report_ignores_jobs_with_no_costs_recorded(jobs):
    """A job with no costs would otherwise report 100% margin and inflate the whole figure —
    the same mistake the old catalog-based margin made, in a different disguise."""
    costed = jobs.create_job(client_name="A", quoted_total=10000)
    jobs.add_job_cost(costed, "Timber", amount=6000)
    jobs.create_job(client_name="B", quoted_total=50000)  # nothing booked

    report = jobs.margin_report(period_days=3650)
    assert report["jobs_total"] == 2
    assert report["jobs_costed"] == 1
    assert report["jobs_without_costs"] == 1
    assert report["quoted_total"] == 10000.0
    assert report["margin"] == 4000.0
    assert report["margin_pct"] == 40.0


def test_margin_report_excludes_cancelled_jobs(jobs):
    cancelled = jobs.create_job(client_name="A", quoted_total=10000)
    jobs.add_job_cost(cancelled, "Timber", amount=6000)
    jobs.update_job(cancelled, status="Cancelled")

    assert jobs.margin_report(period_days=3650)["jobs_total"] == 0


def test_margin_report_on_an_empty_database(jobs):
    report = jobs.margin_report()
    assert report["margin_pct"] == 0.0
    assert report["jobs_total"] == 0


def test_upcoming_lists_jobs_starting_soon(jobs):
    from datetime import datetime, timedelta
    soon = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    far = (datetime.now() + timedelta(days=200)).strftime("%Y-%m-%d")

    jobs.create_job(client_name="Soon", start_date=soon)
    jobs.create_job(client_name="Later", start_date=far)

    names = [j["client_name"] for j in jobs.upcoming_jobs(days=30)]
    assert names == ["Soon"]


def test_upcoming_ignores_completed_work(jobs):
    from datetime import datetime, timedelta
    soon = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    job_id = jobs.create_job(client_name="Done", start_date=soon)
    jobs.update_job(job_id, status="Complete")

    assert jobs.upcoming_jobs(days=30) == []


def test_active_jobs_sort_before_finished_ones(jobs):
    a = jobs.create_job(client_name="Planned")
    b = jobs.create_job(client_name="Running")
    c = jobs.create_job(client_name="Finished")
    jobs.update_job(b, status="In Progress")
    jobs.update_job(c, status="Complete")

    assert [j["client_name"] for j in jobs.get_jobs()] == ["Running", "Planned", "Finished"]
