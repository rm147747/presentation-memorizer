'use client'

import { useCallback, useRef, useState } from 'react'

interface Props {
  onRecordingComplete: (blob: Blob, mimeType: string) => void
  disabled?: boolean
}

export default function AudioRecorder({ onRecordingComplete, disabled = false }: Props) {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const start = useCallback(async () => {
    setError(null)
    setAudioUrl(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      recorderRef.current = mr
      chunksRef.current = []

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mr.onstop = () => {
        const mimeType = mr.mimeType || 'audio/webm'
        const blob = new Blob(chunksRef.current, { type: mimeType })
        const url = URL.createObjectURL(blob)
        setAudioUrl(url)
        onRecordingComplete(blob, mimeType)
        stream.getTracks().forEach((t) => t.stop())
      }

      mr.start()
      setRecording(true)
      setSeconds(0)
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000)
    } catch {
      setError('Não foi possível acessar o microfone. Verifique as permissões do navegador.')
    }
  }, [onRecordingComplete])

  const stop = useCallback(() => {
    recorderRef.current?.stop()
    setRecording(false)
    if (timerRef.current) clearInterval(timerRef.current)
  }, [])

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  return (
    <div className="space-y-3">
      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      <div className="flex items-center gap-3">
        {!recording ? (
          <button
            onClick={start}
            disabled={disabled}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <span className="w-2.5 h-2.5 rounded-full bg-white" />
            Gravar
          </button>
        ) : (
          <button
            onClick={stop}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 text-white text-sm font-medium rounded-lg hover:bg-gray-900 transition-colors"
          >
            <span className="w-2.5 h-2.5 bg-white" />
            Parar — {fmt(seconds)}
          </button>
        )}
        {recording && (
          <span className="flex items-center gap-1.5 text-red-600 text-sm">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            Gravando
          </span>
        )}
      </div>
      {audioUrl && !recording && (
        <audio src={audioUrl} controls className="w-full" />
      )}
    </div>
  )
}
