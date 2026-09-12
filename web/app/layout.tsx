import type { Metadata } from 'next';
import './globals.css';
import './errors.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://foodproof.iyer-vignesh2.chatgpt.site'),
  title: 'FoodProof Fit — Personalized food-label evidence',
  description: 'Scan a packaged-food label and compare the confirmed facts with allergens and daily targets you enter.',
  openGraph: {
    title: 'FoodProof Fit',
    description: 'Your label, made personal.',
    images: ['/og.png'],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'FoodProof Fit',
    description: 'Your label, made personal.',
    images: ['/og.png'],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
