# Odoo plus the parsing and embedding stack the price-intelligence addon needs.
#
# The stock odoo image already carries openpyxl, Pillow, psycopg2 and lxml. What it lacks is
# everything specific to reading a historical quotation archive: PDF extraction, .docx tables,
# fuzzy date parsing, and the ONNX sentence-embedding runtime.
#
# Deliberately no torch. Embeddings run on onnxruntime against a pre-exported
# all-MiniLM-L6-v2 (see tools/export_onnx.py), which is ~90 MB against torch's ~340 MB and
# produced identical vectors on verification.
FROM odoo:19.0-20260803

USER root

# onnxruntime needs a C++ runtime that the slim Odoo base does not ship.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# --break-system-packages: Debian marks the system Python as externally managed, and Odoo's
# image installs its own Python deps there too. A venv would be invisible to the Odoo server
# process, which runs against the system interpreter.
RUN pip3 install --no-cache-dir --break-system-packages \
        onnxruntime==1.19.2 \
        tokenizers==0.22.2 \
        PyMuPDF==1.26.5 \
        python-docx==1.2.0 \
        datefinder==1.0.0 \
        pgvector==0.3.6

USER odoo
