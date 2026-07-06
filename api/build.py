"""
Vercel Python serverless function: build the final .xlsx (step 2 of 2).

Takes the header/rows the user already reviewed in the preview step,
plus the target mode/filename/sheet, and returns the finished spreadsheet.
Re-validates the existing-spreadsheet upload independently, since this is
a separate request from the preview step.
"""

import io
import base64
import logging
from flask import Flask, request, jsonify

from _shared import (
    build_new_workbook,
    append_to_workbook,
    sanitize_filename,
    sanitize_sheet_name,
    MAX_EXISTING_XLSX_BYTES,
    XLSX_MAGIC,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf-build")


@app.route("/api/build", methods=["POST"])
def build():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing request body."}), 400

    header = data.get("header")
    rows = data.get("rows")
    if not header or rows is None:
        return jsonify({"error": "Missing extracted data. Please re-run extraction."}), 400

    mode = data.get("mode", "new")
    sheet_name = sanitize_sheet_name(data.get("sheet_name"))
    filename = sanitize_filename(data.get("filename"))
    existing_b64 = data.get("existing_xlsx_base64")

    existing_bytes = None
    if mode == "append" and existing_b64:
        try:
            existing_bytes = base64.b64decode(existing_b64, validate=True)
        except Exception:
            return jsonify({"error": "The existing spreadsheet data was corrupted in transit."}), 400

        if len(existing_bytes) > MAX_EXISTING_XLSX_BYTES:
            return jsonify({"error": "The existing spreadsheet is too large."}), 400
        if not existing_bytes.startswith(XLSX_MAGIC):
            return jsonify({"error": "That existing file doesn't look like a valid .xlsx spreadsheet."}), 400

    try:
        if mode == "append" and existing_bytes:
            wb = append_to_workbook(existing_bytes, header, rows, sheet_name)
        else:
            wb = build_new_workbook(header, rows, sheet_name)
    except Exception:
        logger.exception("Workbook build failed")
        return jsonify({"error": "Couldn't build the spreadsheet. The existing file may be corrupted or in an unsupported format."}), 400

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    out_b64 = base64.b64encode(buf.read()).decode("utf-8")

    logger.info("Built workbook: mode=%s, sheet=%s, rows=%s, filename=%s", mode, sheet_name, len(rows), filename)

    return jsonify({
        "xlsx_base64": out_b64,
        "filename": filename,
        "row_count": len(rows),
    })
