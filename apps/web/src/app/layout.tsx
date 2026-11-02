import type { Metadata } from "next";
import { Libre_Baskerville, Manrope } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/lib/query-provider";
import { AuthProvider } from "@/features/auth/context/auth-context";

const manrope = Manrope({ subsets: ["latin"], variable: "--font-sans" });
const libreBaskerville = Libre_Baskerville({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-editorial",
});

export const metadata: Metadata = {
  title: {
    default: "Atlas — Healthcare Revenue Recovery",
    template: "%s | Atlas",
  },
  description:
    "A governed healthcare revenue recovery platform for claims, denials, appeals, payments, and accountable operations.",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <body className={`${manrope.variable} ${libreBaskerville.variable} ${manrope.className}`}>
        <QueryProvider>
          <AuthProvider>{children}</AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
