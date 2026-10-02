import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Toaster } from 'react-hot-toast';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'OSINT Nexus - Open Source Intelligence Platform',
  description: 'Advanced OSINT investigation and analysis platform for tracking, analyzing, and visualizing open source intelligence data.',
  keywords: ['OSINT', 'investigation', 'intelligence', 'analysis', 'cybersecurity', 'open source'],
  authors: [{ name: 'OSINT Nexus Team' }],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#1a1f2e',
              color: '#f8fafc',
              border: '1px solid #1e293b',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
            },
            success: {
              iconTheme: {
                primary: '#10b981',
                secondary: '#0a0e17',
              },
            },
            error: {
              iconTheme: {
                primary: '#ef4444',
                secondary: '#0a0e17',
              },
            },
          }}
        />
      </body>
    </html>
  );
}
