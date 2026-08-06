"""One-time export of all-MiniLM-L6-v2 to ONNX, so the shipped app does not need PyTorch.

Run this once on a development machine that has torch installed:

    python tools/export_onnx.py

It writes models/all-MiniLM-L6-v2/{model.onnx,tokenizer.json} and then verifies that the
exported model reproduces sentence-transformers' vectors. Commit the output directory (or
include it in the installer); afterwards `sentence-transformers`, `transformers` and `torch`
can all be dropped from the runtime requirements.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODEL_NAME = "all-MiniLM-L6-v2"
HF_ID = f"sentence-transformers/{MODEL_NAME}"
OUT_DIR = ROOT / "models" / MODEL_NAME

# Cosine similarity below which the export is considered to have changed the model's
# behaviour. Export is numerically lossy at float32; anything above this is rounding.
PARITY_THRESHOLD = 0.9999

SAMPLES = [
    "Pirate Ship",
    "Jungle Gym Playhouse\n10m Height x 5m Length",
    "Additional Transportation + Installation + Crew Cost",
    "BoomTree Twin Platform Playhouse - L7.4 x W4.3 x H3m",
    "",
]


def main():
    import torch
    from transformers import AutoModel, AutoTokenizer

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading {HF_ID} ...")
    tokenizer = AutoTokenizer.from_pretrained(HF_ID)
    model = AutoModel.from_pretrained(HF_ID)
    model.eval()

    tokenizer.save_pretrained(str(OUT_DIR))
    if not (OUT_DIR / "tokenizer.json").exists():
        raise SystemExit(
            "Tokenizer did not save a fast tokenizer.json; the ONNX runtime path needs it."
        )

    sample = tokenizer(["export calibration sentence"], return_tensors="pt",
                       padding=True, truncation=True, max_length=256)
    input_names = ["input_ids", "attention_mask"]
    args = (sample["input_ids"], sample["attention_mask"])
    if "token_type_ids" in sample:
        input_names.append("token_type_ids")
        args = args + (sample["token_type_ids"],)

    print(f"Exporting to {OUT_DIR / 'model.onnx'} ...")
    torch.onnx.export(
        model,
        args,
        str(OUT_DIR / "model.onnx"),
        input_names=input_names,
        output_names=["last_hidden_state"],
        # Batch and sequence length both vary per call, so neither can be baked in.
        dynamic_axes={name: {0: "batch", 1: "sequence"} for name in input_names}
        | {"last_hidden_state": {0: "batch", 1: "sequence"}},
        opset_version=14,
        do_constant_folding=True,
    )

    print("Verifying parity against sentence-transformers ...")
    import numpy as np
    import embedder

    onnx_vectors = embedder.OnnxEmbedder().encode(SAMPLES)
    reference = embedder.SentenceTransformerEmbedder().encode(SAMPLES)

    sims = (onnx_vectors * reference).sum(axis=1)
    worst = float(np.min(sims))
    for text, sim in zip(SAMPLES, sims):
        print(f"  {sim:.6f}  {text[:48]!r}")

    if worst < PARITY_THRESHOLD:
        raise SystemExit(f"Parity check FAILED: worst cosine {worst:.6f} < {PARITY_THRESHOLD}")

    size_mb = (OUT_DIR / "model.onnx").stat().st_size / 1e6
    print(f"\nOK — worst-case cosine {worst:.6f}, model {size_mb:.0f} MB.")
    print("The app will now use the ONNX backend automatically.")
    print("You can drop torch/sentence-transformers from requirements.txt.")


if __name__ == "__main__":
    main()
