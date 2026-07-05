"""
Vercel Python serverless function: PDF -> Excel extraction.
Deployed automatically at /api/extract (Vercel detects .py files in /api).

Reuses the same logic validated in the local extract.py script:
  - real table detection via pdfplumber, first table row promoted to header
  - numeric-looking cells converted to real numbers
  - falls back to raw text lines if no table is found
  - supports "new" (fresh workbook) or "append" (add rows to an uploaded
    existing .xlsx) modes, chosen by the client

Hardening added:
  - rejects payloads with no PDF, or PDFs over the size limit
  - verifies the uploaded bytes actually look like a PDF (magic header)
  - verifies an "existing" append target actually looks like an .xlsx (zip header)
  - catches PDF parsing failures (corrupt/encrypted files) with a clean error
    instead of a raw 500
  - sanitizes the output filename so it can't contain path separators or
    other unsafe characters
"""

import re
import io
import base64
from flask import Flask, request, jsonify
import pdfplumber
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

app = Flask(__name__)

NUMERIC_PATTERN = re.compile(r"^-?\d{1,3}(,\d{3})*(\.\d+)?$|^-?\d+(\.\d+)?$")

MAX_PDF_BYTES = 15 * 1024 * 1024        # 15 MB
MAX_EXISTING_XLSX_BYTES = 15 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
XLSX_MAGIC = b"PK"                      # xlsx files are zip archives


def to_number_if_possible(value):
    if not isinstance(value, str) or value == "":
        return value
    stripped = value.replace(",", "")
    if NUMERIC_PATTERN.match(value):
        try:
            if "." in stripped:
                return float(stripped)
            return int(stripped)
        except ValueError:
            return value
    return value


def extract_rows_from_bytes(pdf_bytes):
    all_rows = []
    header = None
    any_tables_found = False

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()

            if tables:
                any_tables_found = True
                for table in tables:
                    if not table:
                        continue
                    start_idx = 0
                    if header is None:
                        first_row = ["" if c is None else str(c).strip() for c in table[0]]
                        header = ["page"] + first_row
                        start_idx = 1
                    for row in table[start_idx:]:
                        clean_row = ["" if cell is None else str(cell).strip() for cell in row]
                        typed_row = [to_number_if_possible(v) for v in clean_row]
                        all_rows.append([page_num] + typed_row)
            else:
                text = page.extract_text() or ""
                if not text.strip():
                    continue
                if header is None:
                    header = ["page", "text_line"]
                for line in text.split("\n"):
                    if line.strip():
                        all_rows.append([page_num, line.strip()])

    return header, all_rows, any_tables_found


def autosize_columns(ws):
    for col_cells in ws.columns:
        max_len = max((len(str(c.value)) for c in col_cells if c.value is not None), default=10)
        col_letter = get_column_letter(col_cells[0].column)
        ws.column_dimensions[col_letter].width = min(max_len + 2, 60)


def build_new_workbook(header, rows, sheet_name):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(header)
    for row in rows:
        ws.append(row)
    autosize_columns(ws)
    return wb


def append_to_workbook(existing_bytes, header, rows, sheet_name):
    wb = load_workbook(io.BytesIO(existing_bytes))
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        if ws.max_row == 0 or ws.cell(row=1, column=1).value is None:
            ws.append(header)
    else:
        ws = wb.create_sheet(sheet_name)
        ws.append(header)
    for row in rows:
        ws.append(row)
    autosize_columns(ws)
    return wb


def sanitize_filename(name, fallback="extracted_data.xlsx"):
    if not isinstance(name, str) or not name.strip():
        return fallback
    # keep letters, numbers, spaces, dashes, underscores, and a single dot before the extension
    name = name.strip().replace("/", "").replace("\\", "")
    name = re.sub(r"[^A-Za-z0-9 ._-]", "", name)
    name = name.strip(" .")
    if not name:
        return fallback
    if not name.lower().endswith(".xlsx"):
        name += ".xlsx"
    return name[:120]  # keep it reasonable


def sanitize_sheet_name(name, fallback="Extracted"):
    if not isinstance(name, str) or not name.strip():
        return fallback
    # Excel sheet names: no []:*?/\ and max 31 chars
    name = re.sub(r"[\[\]:*?/\\]", "", name).strip()
    return (name or fallback)[:31]


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
        header, rows, used_real_tables = extract_rows_from_bytes(pdf_bytes)
    except Exception:
        return jsonify({
            "error": "Couldn't read this PDF. It may be corrupted, password-protected, or a scanned image without selectable text."
        }), 400

    if header is None:
        return jsonify({"error": "No extractable content found in this PDF."}), 400

    try:
        if mode == "append" and existing_bytes:
            wb = append_to_workbook(existing_bytes, header, rows, sheet_name)
        else:
            wb = build_new_workbook(header, rows, sheet_name)
    except Exception:
        return jsonify({"error": "Couldn't read the existing spreadsheet. It may be corrupted or in an unsupported format."}), 400

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    out_b64 = base64.b64encode(buf.read()).decode("utf-8")

    return jsonify({
        "xlsx_base64": out_b64,
        "filename": filename,
        "row_count": len(rows),
        "used_real_tables": used_real_tables,
    })
