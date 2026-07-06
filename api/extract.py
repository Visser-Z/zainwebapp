"""
Vercel Python serverless function: PDF -> preview (step 1 of 2).

Validates and parses the PDF, returns the extracted header/rows as JSON
so the frontend can show a review table before anything is written.
If an existing spreadsheet is supplied (append mode), also flags how many
of the new rows already appear in that sheet, so the user can catch
accidental re-uploads before confirming.

The actual .xlsx is only built in /api/build, after the user confirms.
"""

import base64
import logging
from flask import Flask, request, jsonify

from _shared import (
    extract_rows_from_bytes,
    get_existing_row_signatures,
    MAX_PDF_BYTES,
    MAX_EXISTING_XLSX_BYTES,
    PDF_MAGIC,
    XLSX_MAGIC,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf-extract")


@app.route("/api/extract", methods=["POST"])
def extract():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing request body."}), 400

    pdf_b64 = data.get("pdf_base64")
    if not pdf_b64:
        return jsonify({"error": "No PDF provided."}), 400

    try:
        pdf_bytes = base64.b64decode(pdf_b64, validate=True)
    except Exception:
        return jsonify({"error": "The PDF data was corrupted in transit. Please try again."}), 400

    if len(pdf_bytes) == 0:
        return jsonify({"error": "The uploaded PDF is empty."}), 400
    if len(pdf_bytes) > MAX_PDF_BYTES:
        return jsonify({"error": f"PDF is too large (max {MAX_PDF_BYTES // (1024 * 1024)} MB)."}), 400
    if not pdf_bytes.startswith(PDF_MAGIC):
        return jsonify({"error": "That file doesn't look like a valid PDF."}), 400

    try:
        header, rows, used_real_tables = extract_rows_from_bytes(pdf_bytes)
    except Exception:
        logger.exception("PDF parsing failed")
        return jsonify({
            "error": "Couldn't read this PDF. It may be corrupted, password-protected, or a scanned image without selectable text."
        }), 400

    if header is None:
        return jsonify({"error": "No extractable content found in this PDF."}), 400

    duplicate_count = 0
    existing_b64 = data.get("existing_xlsx_base64")
    sheet_name = data.get("sheet_name") or "Extracted"

    if existing_b64:
        try:
            existing_bytes = base64.b64decode(existing_b64, validate=True)
        except Exception:
            return jsonify({"error": "The existing spreadsheet data was corrupted in transit."}), 400

        if len(existing_bytes) > MAX_EXISTING_XLSX_BYTES:
            return jsonify({"error": "The existing spreadsheet is too large."}), 400
        if not existing_bytes.startswith(XLSX_MAGIC):
            return jsonify({"error": "That existing file doesn't look like a valid .xlsx spreadsheet."}), 400

        try:
            existing_signatures = get_existing_row_signatures(existing_bytes, sheet_name)
        except Exception:
            return jsonify({"error": "Couldn't read the existing spreadsheet. It may be corrupted."}), 400

        for row in rows:
            sig = tuple(str(v) for v in row)
            if sig in existing_signatures:
                duplicate_count += 1

    logger.info(
        "Preview: %s rows extracted, %s look like duplicates, real_tables=%s",
        len(rows), duplicate_count, used_real_tables,
    )

    return jsonify({
        "header": header,
        "rows": rows,
        "row_count": len(rows),
        "used_real_tables": used_real_tables,
        "duplicate_count": duplicate_count,
    })
