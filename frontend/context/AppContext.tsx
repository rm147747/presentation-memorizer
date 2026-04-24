'use client'

import { createContext, useCallback, useContext, useEffect, useState } from 'react'

interface AppState {
  presId: number | null
  sessionId: number | null
  setPresId: (id: number | null) => void
  setSessionId: (id: number | null) => void
}

const AppContext = createContext<AppState>({
  presId: null,
  sessionId: null,
  setPresId: () => {},
  setSessionId: () => {},
})

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [presId, setPresIdState] = useState<number | null>(null)
  const [sessionId, setSessionIdState] = useState<number | null>(null)

  useEffect(() => {
    const pid = localStorage.getItem('pres_id')
    const sid = localStorage.getItem('session_id')
    if (pid) setPresIdState(JSON.parse(pid))
    if (sid) setSessionIdState(JSON.parse(sid))
  }, [])

  const setPresId = useCallback((id: number | null) => {
    setPresIdState(id)
    if (id === null) localStorage.removeItem('pres_id')
    else localStorage.setItem('pres_id', JSON.stringify(id))
  }, [])

  const setSessionId = useCallback((id: number | null) => {
    setSessionIdState(id)
    if (id === null) localStorage.removeItem('session_id')
    else localStorage.setItem('session_id', JSON.stringify(id))
  }, [])

  return (
    <AppContext.Provider value={{ presId, sessionId, setPresId, setSessionId }}>
      {children}
    </AppContext.Provider>
  )
}

export const useApp = () => useContext(AppContext)
