"""Sentence embeddings, with a runtime that does not require PyTorch.

`sentence-transformers` pulls in torch, which is 339 MB of the 1.0 GB virtualenv and by far
the largest obstacle to shipping this as a desktop installer. The model itself
(all-MiniLM-L6-v2) is 90 MB and runs perfectly well under onnxruntime, which is already a
transitive dependency of chromadb.

So there are two backends:

  * **onnx** — used whenever `models/all-MiniLM-L6-v2/model.onnx` exists. Needs only
    `onnxruntime` and `tokenizers`. This is what a packaged build ships.
  * **sentence-transformers** — the fallback for a dev checkout that has not run the export
    yet. Identical vectors, just a much heavier dependency tree.

Both reproduce the same pipeline — transformer, attention-masked mean pooling, L2
normalization — so vectors are interchangeable and an index built under one backend can be
queried under the other. `tools/export_onnx.py` produces the ONNX file and verifies parity.
"""
import os
from pathlib import Path

import numpy as np

import logging_setup

ROOT = Path(__file__).resolve().parent
MODEL_NAME = "all-MiniLM-L6-v2"
ONNX_DIR = ROOT / "models" / MODEL_NAME
ONNX_MODEL = ONNX_DIR / "model.onnx"
TOKENIZER_JSON = ONNX_DIR / "tokenizer.json"

MAX_TOKENS = 256  # all-MiniLM-L6-v2's trained sequence length

log = logging_setup.get_logger("embedder")

_instance = None


def _mean_pool(token_embeddings, attention_mask):
    """Attention-masked mean pooling, then L2 normalization.

    Padding tokens must be excluded from the average — including them makes a short
    description's vector drift toward the padding embedding, which quietly degrades every
    similarity score computed against it.
    """
    mask = attention_mask[..., None].astype(np.float32)
    summed = (token_embeddings * mask).sum(axis=1)
    counts = np.clip(mask.sum(axis=1), 1e-9, None)
    pooled = summed / counts
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    return pooled / np.clip(norms, 1e-9, None)


class OnnxEmbedder:
    """onnxruntime + tokenizers. No torch."""

    backend = "onnx"

    def __init__(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(TOKENIZER_JSON))
        self.tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self.tokenizer.enable_padding()

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # One thread per physical core is counterproductive here: batches are small and the
        # thread pool spin-up dominates. Leave it to onnxruntime's default heuristics.
        self.session = ort.InferenceSession(str(ONNX_MODEL), options,
                                            providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}

    def encode(self, texts, batch_size=32, show_progress_bar=False):
        single = isinstance(texts, str)
        items = [texts] if single else list(texts)
        if not items:
            return np.zeros((0, 384), dtype=np.float32)

        vectors = []
        for start in range(0, len(items), batch_size):
            chunk = [str(t or "") for t in items[start:start + batch_size]]
            encodings = self.tokenizer.encode_batch(chunk)
            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

            feed = {"input_ids": input_ids, "attention_mask": attention_mask}
            if "token_type_ids" in self.input_names:
                feed["token_type_ids"] = np.array([e.type_ids for e in encodings], dtype=np.int64)

            token_embeddings = self.session.run(None, feed)[0]
            vectors.append(_mean_pool(token_embeddings, attention_mask))

        out = np.vstack(vectors).astype(np.float32)
        return out[0] if single else out


class SentenceTransformerEmbedder:
    """The original backend, kept for dev checkouts that have not exported the ONNX model."""

    backend = "sentence-transformers"

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(MODEL_NAME)

    def encode(self, texts, batch_size=32, show_progress_bar=False):
        # normalize_embeddings mirrors what the ONNX path does by hand, so the two backends
        # produce directly comparable vectors.
        return self.model.encode(
            texts, batch_size=batch_size, show_progress_bar=show_progress_bar,
            normalize_embeddings=True,
        )


def onnx_available():
    return ONNX_MODEL.exists() and TOKENIZER_JSON.exists()


def get_embedder(force_backend=None):
    """Returns the process-wide embedder, loading it on first use.

    Lazy because loading costs a second or two and the app should paint its window first;
    a PM browsing history or the catalog never touches the model at all.
    """
    global _instance
    if _instance is not None and force_backend in (None, _instance.backend):
        return _instance

    backend = force_backend or os.environ.get("QE_EMBEDDER") or ("onnx" if onnx_available() else "st")

    if backend == "onnx":
        if not onnx_available():
            raise RuntimeError(
                f"ONNX model not found at {ONNX_MODEL}. Run: python tools/export_onnx.py"
            )
        log.info("Loading embedding model (%s, onnxruntime)", MODEL_NAME)
        _instance = OnnxEmbedder()
    else:
        log.info("Loading embedding model (%s, sentence-transformers)", MODEL_NAME)
        _instance = SentenceTransformerEmbedder()

    return _instance
