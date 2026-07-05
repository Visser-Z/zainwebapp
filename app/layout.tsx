import "./globals.css";

export const metadata = {
  title: "PDF to Excel",
  description: "Extract tables from PDF invoices into Excel.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
