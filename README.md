# PDF to Excel Web App

Drag in a PDF, get a downloadable Excel spreadsheet with the extracted table
data — either as a new file or appended to an existing one.

## Stack

- **Frontend**: Next.js (App Router), plain CSS, no external UI libraries
- **Backend**: Python serverless function (`/api/extract.py`) running on
  Vercel's Python runtime — reuses the exact pdfplumber/openpyxl logic
  already validated in the standalone `extract.py` script
- **Deploy target**: Vercel (same as your other projects)

## Local development

1. Install frontend deps:
   ```
   npm install
   ```

2. Install Python deps (for local API testing via `vercel dev`):
   ```
   py -m pip install -r requirements.txt
   ```

3. Run locally. Because this app mixes a Next.js frontend with a Python
   serverless function, use the Vercel CLI locally instead of plain
   `next dev`, so the `/api/extract` route actually works:
   ```
   npm install -g vercel
   vercel dev
   ```
   This serves the app (usually at http://localhost:3000) with both the
   Next.js frontend and the Python function running together.

## Deploy

```
vercel
```
Follow the prompts to link/create the project, then `vercel --prod` to push
to production. No environment variables are required for the current
feature set.

## How append mode works

The "Add to existing" option requires the user to also upload their current
`.xlsx` in the same request. The server loads it, finds (or creates) the
named sheet, and appends the new rows to the end. Nothing is stored
server-side — every request is stateless.

## Where to extend next

- **Layout variance**: if a client's real PDFs don't have consistent table
  structure, add a fallback in `api/extract.py` that calls the Claude API
  (PDF input + structured JSON output) when `used_real_tables` comes back
  false, instead of just returning raw text lines.
- **Persistent spreadsheets**: swap the "upload existing .xlsx" step for a
  Supabase-stored file per client, so users don't need to re-upload it each
  time — same storage pattern as the Meri POD project.
- **Multi-file batches**: currently one PDF per request; batching multiple
  PDFs into one append run is a straightforward loop extension on both the
  frontend and `api/extract.py`.
