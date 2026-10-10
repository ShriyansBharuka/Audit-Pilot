import type { Metadata } from "next";
import { Fira_Code, Fira_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { Navigation } from "@/components/Navigation";

// Fira Sans + Fira Code: the ui-ux-pro-max pairing for data dashboards (globals.css maps them to font-sans/mono)
const firaSans = Fira_Sans({
  variable: "--font-fira-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const firaCode = Fira_Code({
  variable: "--font-fira-code",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AuditPilot AI — Statutory Revenue Audit",
  description:
    "AI-run statutory revenue audit platform with tamper-evident ledger, 100% population testing (D0-D14), AuditGraph risk scoring, SHAP explainability, and Supabase RBAC.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${firaSans.variable} ${firaCode.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider>
          <Navigation>{children}</Navigation>
        </AuthProvider>
      </body>
    </html>
  );
}
