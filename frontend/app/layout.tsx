import type { Metadata } from 'next'
import './globals.css'
import Nav from '@/components/Nav'
import { AppProvider } from '@/context/AppContext'

export const metadata: Metadata = {
  title: 'Memorizar Apresentação',
  description: 'Sistema de memorização com degradação progressiva',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-gray-50">
        <AppProvider>
          <Nav />
          <main className="max-w-5xl mx-auto px-4 py-8">{children}</main>
        </AppProvider>
      </body>
    </html>
  )
}
