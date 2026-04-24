'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useApp } from '@/context/AppContext'

const links = [
  { href: '/', label: '📄 Nova Apresentação' },
  { href: '/train', label: '🎯 Treinar' },
  { href: '/report', label: '📊 Relatório' },
]

export default function Nav() {
  const pathname = usePathname()
  const { presId, sessionId } = useApp()

  return (
    <nav className="bg-white border-b shadow-sm sticky top-0 z-10">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                pathname === href
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
        <div className="flex gap-2 text-xs">
          {presId && (
            <span className="bg-green-50 text-green-700 border border-green-200 px-2 py-1 rounded-full">
              Apresentação #{presId}
            </span>
          )}
          {sessionId && (
            <span className="bg-blue-50 text-blue-700 border border-blue-200 px-2 py-1 rounded-full">
              Sessão #{sessionId}
            </span>
          )}
        </div>
      </div>
    </nav>
  )
}
