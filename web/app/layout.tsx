import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://foodproof.iyer-vignesh2.chatgpt.site'),
  title: 'FoodProof — Understand your food label',
  description: 'Scan a packaged-food label and get a clear, evidence-backed nutrition explanation.',
  openGraph: {
    title: 'FoodProof',
    description: 'Your label, made useful.',
    images: ['/og.png'],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'FoodProof',
    description: 'Your label, made useful.',
    images: ['/og.png'],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
