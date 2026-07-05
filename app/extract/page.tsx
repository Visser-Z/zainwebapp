"use client";

import { useState, useRef } from "react";

type Mode = "new" | "append";

const MAX_PDF_MB = 15;
const MAX_XLSX_MB = 15;

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function ExtractPage() {
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [existingFile, setExistingFile] = useState<File | null>(null);
  const [mode, setMode] = useState<Mode>("new");
  const [outputName, setOutputName] = useState("extracted_data.xlsx");
  const [sheetName, setSheetName] = useState("Extracted");
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{ type: "error" | "success" | "info"; message: string } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const acceptPdf = (file: File) => {
    if (file.type !== "application/pdf") {
      setStatus({ type: "error", message: "Please choose a PDF file." });
      return;
    }
    if (file.size > MAX_PDF_MB * 1024 * 1024) {
      setStatus({ type: "error", message: `PDF is too large — max ${MAX_PDF_MB} MB.` });
      return;
    }
    setPdfFile(file);
    setStatus(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) acceptPdf(file);
  };

  const handleSubmit = async () => {
    if (!pdfFile) {
      setStatus({ type: "error", message: "Choose a PDF first." });
      return;
    }
    if (mode === "append" && !existingFile) {
      setStatus({ type: "error", message: "Choose the existing spreadsheet to append to, or switch to 'New spreadsheet'." });
      return;
    }

    setLoading(true);
    setStatus({ type: "info", message: "Extracting..." });

    try {
      const pdf_base64 = await fileToBase64(pdfFile);
      const existing_xlsx_base64 = existingFile ? await fileToBase64(existingFile) : null;

      const res = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pdf_base64,
          existing_xlsx_base64,
          mode,
          filename: outputName.endsWith(".xlsx") ? outputName : `${outputName}.xlsx`,
          sheet_name: sheetName || "Extracted",
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Unknown error" }));
        throw new Error(err.error || "Extraction failed.");
      }

      const data = await res.json();
      const byteChars = atob(data.xlsx_base64);
      const byteNumbers = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
      const blob = new Blob([new Uint8Array(byteNumbers)], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = data.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      setStatus({
        type: "success",
        message: `Done — ${data.row_count} rows ${mode === "append" ? "added" : "written"}.${
          data.used_real_tables ? "" : " (No table structure detected — rows are raw text lines.)"
        }`,
      });
    } catch (err: any) {
      setStatus({ type: "error", message: err.message || "Something went wrong." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="eyebrow">PDF → Excel</div>
      <h1>Extract invoice data into a spreadsheet</h1>
      <p className="subtitle">Drop in a PDF, choose a new or existing spreadsheet, and download the result.</p>

      <div className="card">
        <div
          className={`dropzone ${dragActive ? "active" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <p>{pdfFile ? "Drop a different PDF, or click to browse" : "Drag a PDF here, or click to browse"}</p>
          {pdfFile && <div className="filename">{pdfFile.name}</div>}
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) acceptPdf(file);
            }}
          />
        </div>

        <div className="field">
          <label>Spreadsheet</label>
          <div className="mode-toggle">
            <button
              type="button"
              className={mode === "new" ? "selected" : ""}
              onClick={() => setMode("new")}
            >
              New spreadsheet
            </button>
            <button
              type="button"
              className={mode === "append" ? "selected" : ""}
              onClick={() => setMode("append")}
            >
              Add to existing
            </button>
          </div>
        </div>

        {mode === "append" && (
          <div className="field">
            <label>Existing spreadsheet (.xlsx)</label>
            <input
              type="file"
              accept=".xlsx"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                if (file.size > MAX_XLSX_MB * 1024 * 1024) {
                  setStatus({ type: "error", message: `Spreadsheet is too large — max ${MAX_XLSX_MB} MB.` });
                  return;
                }
                setExistingFile(file);
              }}
            />
            <div className="hint">Rows from this PDF will be added to the end of this file.</div>
          </div>
        )}

        <div className="field">
          <label>Output file name</label>
          <input
            type="text"
            value={outputName}
            onChange={(e) => setOutputName(e.target.value)}
            placeholder="extracted_data.xlsx"
          />
        </div>

        <div className="field">
          <label>Sheet name</label>
          <input
            type="text"
            value={sheetName}
            onChange={(e) => setSheetName(e.target.value)}
            placeholder="Extracted"
          />
        </div>

        <button className="submit-btn" onClick={handleSubmit} disabled={loading}>
          {loading ? "Extracting..." : "Extract and download"}
        </button>

        {status && <div className={`status ${status.type}`}>{status.message}</div>}
      </div>
    </div>
  );
}
