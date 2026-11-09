import './globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = {
  title: 'Crypto Market Intelligence',
  description: 'Daily market data and cautious crypto analysis',
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
