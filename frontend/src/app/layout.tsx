import type { Metadata } from "next";
export const metadata: Metadata = {title: "Uploadio", description: "Your publishing workspace"};
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}
