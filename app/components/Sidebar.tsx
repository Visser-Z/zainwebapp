"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/extract", label: "Extract PDF" },
  { href: "#", label: "Shipments", disabled: true },
  { href: "#", label: "Stock", disabled: true },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">SY</div>
        <div className="brand-name">Saga Yasuo</div>
      </div>
      <nav className="nav">
        {NAV_ITEMS.map((item) =>
          item.disabled ? (
            <span key={item.label} className="nav-item nav-item-disabled">
              {item.label}
              <span className="nav-tag">soon</span>
            </span>
          ) : (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${pathname === item.href ? "nav-item-active" : ""}`}
            >
              {item.label}
            </Link>
          )
        )}
      </nav>
    </aside>
  );
}
