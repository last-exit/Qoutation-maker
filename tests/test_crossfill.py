"""Photo cross-fill: borrowing a picture from the nearest photographed twin.

Restructured into one batched matmul, so these pin the behaviour that used to live in a
per-item loop.
"""
import warnings

import numpy as np

import app


def unit_vectors(*rows):
    arr = np.asarray(rows, dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


def make_items(specs):
    return [
        {"original_description": desc, "image_ref": ref, "file_name": "source.xlsx"}
        for desc, ref in specs
    ]


def test_borrows_from_the_nearest_photographed_item():
    items = make_items([("Pirate Ship", "a" * 64), ("Pirate Ship Large", "")])
    # Near-identical directions, comfortably above CROSSFILL_AUTO.
    embeddings = unit_vectors([1.0, 0.0, 0.0], [0.99, 0.14, 0.0])

    assert app.crossfill_images(items, embeddings) == 1
    assert items[1]["image_ref"] == "a" * 64
    assert items[1]["image_source"].startswith("matched from")


def test_distant_items_are_left_without_a_photo():
    items = make_items([("Pirate Ship", "a" * 64), ("Accounting Software Licence", "")])
    embeddings = unit_vectors([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])

    assert app.crossfill_images(items, embeddings) == 0
    assert items[1]["image_ref"] == ""


def test_middling_confidence_is_labelled_as_suggested():
    items = make_items([("Pirate Ship", "a" * 64), ("Wooden boat structure", "")])
    # Cosine ~0.75: between CROSSFILL_SUGGEST and CROSSFILL_AUTO.
    embeddings = unit_vectors([1.0, 0.0, 0.0], [0.75, 0.66, 0.0])

    assert app.crossfill_images(items, embeddings) == 1
    assert items[1]["image_source"].startswith("suggested from")


def test_service_lines_never_borrow_a_product_photo():
    """This is how "Delivery" ended up showing a photo lifted from a furniture quotation."""
    items = make_items([("Pirate Ship", "a" * 64), ("Delivery and installation", "")])
    embeddings = unit_vectors([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])

    assert app.crossfill_images(items, embeddings) == 0
    assert items[1]["image_ref"] == ""


def test_each_item_picks_its_own_best_source():
    """The batched matmul must keep rows and columns aligned — a transpose slip here would
    hand every item the same photo."""
    items = make_items([
        ("Ship", "ship" + "0" * 60),
        ("Tower", "towr" + "0" * 60),
        ("Ship variant", ""),
        ("Tower variant", ""),
    ])
    embeddings = unit_vectors(
        [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.99, 0.14, 0.0], [0.14, 0.99, 0.0]
    )

    assert app.crossfill_images(items, embeddings) == 2
    assert items[2]["image_ref"] == "ship" + "0" * 60
    assert items[3]["image_ref"] == "towr" + "0" * 60


def test_no_photographed_items_is_a_no_op():
    items = make_items([("Pirate Ship", ""), ("Tower", "")])
    assert app.crossfill_images(items, unit_vectors([1.0, 0.0], [0.0, 1.0])) == 0


def test_mismatched_embedding_count_is_rejected():
    """Silently borrowing against misaligned vectors would attach arbitrary photos."""
    items = make_items([("Pirate Ship", "a" * 64), ("Tower", "")])
    assert app.crossfill_images(items, unit_vectors([1.0, 0.0])) == 0


def test_emits_no_numerical_warnings():
    """Accelerate's BLAS raises spurious FP-status warnings; they must not reach the log."""
    items = make_items([("Pirate Ship", "a" * 64)] + [(f"Item {i}", "") for i in range(60)])
    rng = np.random.default_rng(0)
    embeddings = rng.normal(size=(61, 384)).astype(np.float32)
    embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        app.crossfill_images(items, embeddings)

    assert [str(w.message) for w in caught if issubclass(w.category, RuntimeWarning)] == []
