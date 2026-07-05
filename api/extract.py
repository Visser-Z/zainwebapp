"""
Vercel Python serverless function: PDF -> Excel extraction.
Deployed automatically at /api/extract (Vercel detects .py files in /api).

Reuses the same logic validated in the local extract.py script:
  - real table detection via pdfplumber, first table row promoted to header
  - numeric-looking cells converted to real numbers
  - falls back to raw text lines if no table is found
  - supports "new" (fresh workbook) or "append" (add rows to an uploaded
    existing .xlsx) modes, chosen by the client
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


@app.route("/api/extract", methods=["POST"])
def extract():
    data = request.get_json(force=True)

    pdf_b64 = data.get("pdf_base64")
    if not pdf_b64:
        return jsonify({"error": "No PDF provided."}), 400

    mode = data.get("mode", "new")
    sheet_name = data.get("sheet_name") or "Extracted"
    filename = data.get("filename") or "extracted_data.xlsx"
    existing_b64 = data.get("existing_xlsx_base64")

    pdf_bytes = base64.b64decode(pdf_b64)
    header, rows, used_real_tables = extract_rows_from_bytes(pdf_bytes)

    if header is None:
        return jsonify({"error": "No extractable content found in this PDF."}), 400

    if mode == "append" and existing_b64:
        existing_bytes = base64.b64decode(existing_b64)
        wb = append_to_workbook(existing_bytes, header, rows, sheet_name)
    else:
        wb = build_new_workbook(header, rows, sheet_name)

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
