import type { Metadata } from "next";
import { Inter, Noto_Sans_Armenian } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const notoArmenian = Noto_Sans_Armenian({
  subsets: ["armenian"],
  variable: "--font-armenian",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "ART Արտադրություն",
  description: "Բարձրակարգ հագուստի արտադրության հարթակ",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="hy">
      <body className={`${inter.variable} ${notoArmenian.variable} font-sans`}>{children}</body>
    </html>
  );
}
