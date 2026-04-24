'use client'

import { useRef, useState } from 'react'
import AudioRecorder from '@/components/AudioRecorder'
import { useApp } from '@/context/AppContext'
import { api, ApiError } from '@/lib/api'
import type { Presentation, ReferenceAudioResponse } from '@/lib/types'

export default function NovaApresentacaoPage() {
  const { presId, setPresId } = useApp()

  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [savedPres, setSavedPres] = useState<Presentation | null>(null)

  const [audioBlob, setAudioBlob] = useState<{ blob: Blob; mime: string } | null>(null)
  const [transcribing, setTranscribing] = useState(false)
  const [refResult, setRefResult] = useState<ReferenceAudioResponse | null>(null)
  const [refError, setRefError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const content = ev.target?.result as string
      setText(content)
    }
    reader.readAsText(file, 'utf-8')
  }

  async function handleSave() {
    setSaving(true)
    setSaveError(null)
    try {
      const pres = await api.post<Presentation>('/presentations/', { title, text })
      setSavedPres(pres)
      setPresId(pres.id)
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Erro ao salvar apresentação.')
    } finally {
      setSaving(false)
    }
  }

  async function handleTranscribe() {
    const activePres = savedPres ?? (presId ? { id: presId } : null)
    if (!activePres || !audioBlob) return
    setTranscribing(true)
    setRefError(null)
    setRefResult(null)
    try {
      const form = new FormData()
      const ext = audioBlob.mime.includes('webm') ? 'webm' : 'wav'
      form.append('audio', new File([audioBlob.blob], `reference.${ext}`, { type: audioBlob.mime }))
      const result = await api.postForm<ReferenceAudioResponse>(
        `/presentations/${activePres.id}/reference-audio`,
        form
      )
      setRefResult(result)
    } catch (err) {
      setRefError(err instanceof ApiError ? err.message : 'Erro ao transcrever áudio.')
    } finally {
      setTranscribing(false)
    }
  }

  function handleAudioFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) setAudioBlob({ blob: file, mime: file.type })
  }

  const activePres = savedPres ?? (presId ? { id: presId } : null)
  const canSave = title.trim().length > 0 && text.trim().length > 0

  return (
    <div className="space-y-8">
      {/* Section 1: Apresentação */}
      <div className="card">
        <h2 className="section-title">1. Apresentação</h2>

        <div className="space-y-4">
          <div>
            <label className="label">Título</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Nome da apresentação"
              className="input"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="label">Texto (um parágrafo por linha)</label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-xs text-indigo-600 hover:underline"
              >
                Importar .txt
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt"
              className="hidden"
              onChange={handleFileUpload}
            />
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Cole o texto aqui. Cada linha vira um segmento."
              rows={10}
              className="input resize-y font-mono text-xs"
            />
          </div>

          {saveError && <p className="alert-error">{saveError}</p>}

          {savedPres && (
            <p className="alert-success">
              Salvo! ID #{savedPres.id} · {savedPres.segment_count} segmento(s)
            </p>
          )}

          <button
            onClick={handleSave}
            disabled={!canSave || saving}
            className="btn-primary"
          >
            {saving ? 'Salvando…' : 'Salvar Apresentação'}
          </button>
        </div>
      </div>

      {/* Section 2: Gravação de Referência */}
      <div className="card">
        <h2 className="section-title">2. Gravação de Referência</h2>
        <p className="text-sm text-gray-500 mb-6">
          Leia o texto em voz alta. O Whisper transcreve e alinha cada palavra com seu timestamp.
        </p>

        {!activePres && (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 mb-4">
            Salve uma apresentação primeiro para habilitar a gravação de referência.
          </p>
        )}

        <div className="space-y-4">
          <div>
            <label className="label">Gravar pelo microfone</label>
            <AudioRecorder
              onRecordingComplete={(blob, mime) => setAudioBlob({ blob, mime })}
              disabled={!activePres}
            />
          </div>

          <div className="flex items-center gap-3">
            <hr className="flex-1 border-gray-200" />
            <span className="text-xs text-gray-400">ou</span>
            <hr className="flex-1 border-gray-200" />
          </div>

          <div>
            <label className="label">Enviar arquivo de áudio</label>
            <input
              type="file"
              accept=".wav,.mp3,.m4a,.webm,.ogg"
              disabled={!activePres}
              onChange={handleAudioFileUpload}
              className="text-sm text-gray-600 file:btn-secondary file:mr-3 file:cursor-pointer disabled:opacity-50"
            />
            {audioBlob && (
              <p className="text-xs text-gray-500 mt-1">
                Áudio pronto ({(audioBlob.blob.size / 1024).toFixed(0)} KB)
              </p>
            )}
          </div>

          {refError && <p className="alert-error">{refError}</p>}

          {refResult && (
            <div className="alert-success space-y-1">
              <p>
                Referência salva · idioma: <strong>{refResult.language}</strong> ·{' '}
                {refResult.segments} segmentos · cobertura: {refResult.coverage_pct.toFixed(0)}%
              </p>
              <p className="text-xs text-green-600 font-mono">{refResult.transcript}</p>
            </div>
          )}

          <button
            onClick={handleTranscribe}
            disabled={!activePres || !audioBlob || transcribing}
            className="btn-primary"
          >
            {transcribing ? 'Transcrevendo com Whisper…' : 'Transcrever Referência'}
          </button>
        </div>
      </div>
    </div>
  )
}
