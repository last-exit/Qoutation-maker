"""Index identity and the embedding backend."""
import numpy as np
import pytest


# --- Content-hash item ids -------------------------------------------------------------

def item(desc="Pirate Ship", rate=100.0, file_name="Cost Sheet.xlsx"):
    return {"original_description": desc, "historical_rate": rate, "file_name": file_name}


def test_id_is_stable_across_rebuilds():
    """Ids used to be `item_{position}`, so a re-sync could land a PM's correction on a
    different product entirely."""
    import app
    assert app._item_id(item()) == app._item_id(item())


def test_id_is_independent_of_position():
    import app
    ids_run_one = [app._item_id(item(desc=d)) for d in ("A", "B", "C")]
    ids_run_two = [app._item_id(item(desc=d)) for d in ("C", "B", "A")]
    assert set(ids_run_one) == set(ids_run_two)


@pytest.mark.parametrize("changed", [
    {"desc": "Different Product"},
    {"rate": 999.0},
    {"file_name": "Other Sheet.xlsx"},
])
def test_id_changes_when_the_item_changes(changed):
    import app
    assert app._item_id(item()) != app._item_id(item(**changed))


def test_id_ignores_case_and_padding():
    import app
    assert app._item_id(item(desc="  PIRATE SHIP ")) == app._item_id(item(desc="pirate ship"))


# --- Embedder --------------------------------------------------------------------------

def test_embeddings_are_unit_normalized():
    """_distance_to_similarity converts squared L2 into cosine assuming unit vectors; the
    similarity percentage shown to the PM is wrong if they are not."""
    import embedder

    vectors = embedder.get_embedder().encode(["Pirate Ship", "Jungle Gym"])
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4)


def test_related_text_scores_above_unrelated():
    import embedder

    model = embedder.get_embedder()
    ship, boat, invoice = model.encode(["Pirate Ship", "wooden pirate boat", "VAT invoice terms"])
    assert float(ship @ boat) > float(ship @ invoice)


def test_encoding_a_single_string_returns_one_vector():
    import embedder
    assert embedder.get_embedder().encode("Pirate Ship").shape == (384,)


def test_empty_input_returns_empty_array():
    import embedder
    assert embedder.get_embedder().encode([]).shape[0] == 0


def test_batching_matches_single_pass():
    """Padding is masked out of the mean pool, so batch composition must not move a vector."""
    import embedder

    model = embedder.get_embedder()
    texts = ["short", "a considerably longer description with many more tokens in it", "mid"]
    batched = model.encode(texts, batch_size=2)
    one_at_a_time = np.vstack([model.encode([t])[0] for t in texts])
    assert np.allclose(batched, one_at_a_time, atol=1e-4)


# --- Similarity conversion --------------------------------------------------------------

def test_distance_to_similarity_endpoints():
    import app
    assert app._distance_to_similarity(0.0) == 100.0   # identical
    assert app._distance_to_similarity(2.0) == 0.0     # orthogonal
    assert app._distance_to_similarity(4.0) == 0.0     # opposite, clamped


def test_distance_to_similarity_survives_garbage():
    import app
    assert app._distance_to_similarity(None) == 0.0


# --- Fresh install ----------------------------------------------------------------------

def test_model_is_fetched_when_missing(tmp_path, monkeypatch):
    """A fresh clone has no models/ directory and no torch. Without the download it installs
    cleanly and then cannot search at all."""
    import embedder

    monkeypatch.setattr(embedder, "ONNX_DIR", tmp_path / "all-MiniLM-L6-v2")
    monkeypatch.setattr(embedder, "ONNX_MODEL", tmp_path / "all-MiniLM-L6-v2" / "model.onnx")
    monkeypatch.setattr(embedder, "TOKENIZER_JSON", tmp_path / "all-MiniLM-L6-v2" / "tokenizer.json")
    assert embedder.onnx_available() is False

    fetched = []

    def fake_retrieve(url, destination):
        fetched.append(url)
        # Big enough to clear the truncation guard.
        open(destination, "wb").write(b"x" * (embedder.MIN_MODEL_BYTES + 1))

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlretrieve", fake_retrieve)

    assert embedder.download_model() is True
    assert len(fetched) == 2
    assert embedder.onnx_available() is True


def test_a_truncated_download_is_rejected(tmp_path, monkeypatch):
    """A half-file cached in place would fail confusingly at load time instead."""
    import embedder

    monkeypatch.setattr(embedder, "ONNX_DIR", tmp_path / "m")
    monkeypatch.setattr(embedder, "ONNX_MODEL", tmp_path / "m" / "model.onnx")
    monkeypatch.setattr(embedder, "TOKENIZER_JSON", tmp_path / "m" / "tokenizer.json")

    def short_retrieve(url, destination):
        open(destination, "wb").write(b"x" * 5000)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlretrieve", short_retrieve)

    with pytest.raises(RuntimeError, match="truncated"):
        embedder.download_model()
    assert not embedder.ONNX_MODEL.exists(), "the bad file must not be left behind"


def test_fresh_install_chooses_onnx_and_downloads(tmp_path, monkeypatch):
    """Falling back to sentence-transformers when the model is absent would pick a backend
    whose dependency is not installed, and the download would never fire."""
    import embedder

    monkeypatch.setattr(embedder, "ONNX_DIR", tmp_path / "m")
    monkeypatch.setattr(embedder, "ONNX_MODEL", tmp_path / "m" / "model.onnx")
    monkeypatch.setattr(embedder, "TOKENIZER_JSON", tmp_path / "m" / "tokenizer.json")
    monkeypatch.setattr(embedder, "_instance", None)
    monkeypatch.delenv("QE_EMBEDDER", raising=False)

    called = []
    monkeypatch.setattr(embedder, "download_model", lambda *a, **k: called.append(1))
    # Stop before the real session load; the choice of backend is what is under test.
    monkeypatch.setattr(embedder, "OnnxEmbedder", lambda: type("E", (), {"backend": "onnx"})())

    assert embedder.get_embedder().backend == "onnx"
    assert called, "the missing model should have triggered a download"
