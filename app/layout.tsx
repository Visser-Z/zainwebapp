import "./globals.css";
import Sidebar from "./components/Sidebar";
import Footer from "./components/Footer";

export const metadata = {
  title: "Saga Yasuo | Dashboard",
  description: "Extract invoice data into Excel, with tracking features on the way.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <Sidebar />
          <main className="main">{children}</main>
        </div>
        <Footer />
      </body>
    </html>
  );
}
