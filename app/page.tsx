import Link from "next/link";

export default function DashboardHome() {
  return (
    <div className="page">
      <div className="eyebrow">Overview</div>
      <h1>Dashboard</h1>
      <p className="subtitle">Everything starts with getting your paperwork into a spreadsheet. Tracking features land here next.</p>

      <div className="grid">
        <Link href="/extract" className="tile tile-active">
          <div className="tile-label">Available now</div>
          <div className="tile-title">Extract PDF → Excel</div>
          <div className="tile-desc">Turn invoices and shipping docs into spreadsheet rows.</div>
        </Link>

        <div className="tile tile-soon">
          <div className="tile-label">Coming soon</div>
          <div className="tile-title">Shipments tracker</div>
          <div className="tile-desc">See every shipment, status, and value in one place.</div>
        </div>

        <div className="tile tile-soon">
          <div className="tile-label">Coming soon</div>
          <div className="tile-title">Stock overview</div>
          <div className="tile-desc">Cartons in, cartons out, by fruit and origin.</div>
        </div>

        <div className="tile tile-soon">
          <div className="tile-label">Coming soon</div>
          <div className="tile-title">Reports</div>
          <div className="tile-desc">Weekly and monthly summaries, ready to export.</div>
        </div>
      </div>
    </div>
  );
}
