'use client'

import { useState } from 'react'
import AudioRecorder from '@/components/AudioRecorder'
import DiffView from '@/components/DiffView'
import HeatMap from '@/components/HeatMap'
import { useApp } from '@/context/AppContext'
import { api, ApiError } from '@/lib/api'
import type { AttemptResult, DegradationResponse, ScheduleData, SessionResponse } from '@/lib/types'

const LEVEL_LABEL: Record<number, string> = {
  1: 'Texto completo',
  2: 'Lacunas (30%)',
  3: 'Primeira palavra',
  4: 'Tela em branco',
}

export default function TreinarPage() {
  const { presId, setPresId, setSessionId, sessionId } = useApp()

  const [inputPresId, setInputPresId] = useState(presId ?? 1)
  const [level, setLevel] = useState(1)
  const [segIndex, setSegIndex] = useState(0)
  const [originalText, setOriginalText] = useState('')
  const [degraded, setDegraded] = useState<DegradationResponse | null>(null)
  const [attemptAudio, setAttemptAudio] = useState<{ blob: Blob; mime: string } | null>(null)
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null)
  const [schedule, setSchedule] = useState<ScheduleData | null>(null)

  const [sessionLoading, setSessionLoading] = useState(false)
  const [degradeLoading, setDegradeLoading] = useState(false)
  const [attemptLoading, setAttemptLoading] = useState(false)
  const [scheduleLoading, setScheduleLoading] = useState(false)

  const [error, setError] = useState<string | null>(null)

  function setErr(msg: unknown) {
    if (msg instanceof Error) setError(msg.message)
    else setError(String(msg))
  }

  async function handleNewSession() {
    setSessionLoading(true)
    setError(null)
    setAttemptResult(null)
    setSchedule(null)
    try {
      const pid = inputPresId
      setPresId(pid)
      // sessions/ uses query params
      const params = new URLSearchParams({ presentation_id: String(pid), level: String(level) })
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/sessions/?${params}`,
        { method: 'POST' }
      )
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        const detail = Array.isArray(j.detail)
          ? j.detail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join('; ')
          : (j.detail ?? res.statusText)
        throw new ApiError(res.status, detail)
      }
      const data: SessionResponse = await res.json()
      setSessionId(data.session_id)
    } catch (err) {
      setErr(err)
    } finally {
      setSessionLoading(false)
    }
  }

  async function handleDegrade() {
    if (!originalText.trim()) return
    setDegradeLoading(true)
    setError(null)
    try {
      const result = await api.post<DegradationResponse>('/degrade', {
        text: originalText,
        level,
        seed: 42,
      })
      setDegraded(result)
    } catch (err) {
      setErr(err)
    } finally {
      setDegradeLoading(false)
    }
  }

  function handleAttemptFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) setAttemptAudio({ blob: file, mime: file.type })
  }

  async function handleAnalyze() {
    if (!sessionId || !attemptAudio) return
    setAttemptLoading(true)
    setError(null)
    setAttemptResult(null)
    try {
      const form = new FormData()
      const ext = attemptAudio.mime.includes('webm') ? 'webm' : 'wav'
      form.append(
        'audio',
        new File([attemptAudio.blob], `attempt.${ext}`, { type: attemptAudio.mime })
      )
      const result = await api.postForm<AttemptResult>(
        `/sessions/${sessionId}/attempt`,
        form,
        { segment_index: String(segIndex) }
      )
      setAttemptResult(result)
    } catch (err) {
      setErr(err)
    } finally {
      setAttemptLoading(false)
    }
  }

  async function handleSchedule() {
    const pid = presId ?? inputPresId
    setScheduleLoading(true)
    setError(null)
    try {
      const data = await api.get<ScheduleData>(`/presentations/${pid}/schedule`)
      setSchedule(data)
    } catch (err) {
      setErr(err)
    } finally {
      setScheduleLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Config */}
      <div className="card">
        <h2 className="section-title">Configuração</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="label">Apresentação ID</label>
            <input
              type="number"
              min={1}
              value={inputPresId}
              onChange={(e) => setInputPresId(Number(e.target.value))}
              className="input"
            />
          </div>
          <div>
            <label className="label">Nível</label>
            <select
              value={level}
              onChange={(e) => setLevel(Number(e.target.value))}
              className="input"
            >
              {[1, 2, 3, 4].map((l) => (
                <option key={l} value={l}>
                  {l} — {LEVEL_LABEL[l]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Segmento</label>
            <input
              type="number"
              min={0}
              value={segIndex}
              onChange={(e) => setSegIndex(Number(e.target.value))}
              className="input"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={handleNewSession}
              disabled={sessionLoading}
              className="btn-primary w-full"
            >
              {sessionLoading ? 'Criando…' : 'Nova Sessão'}
            </button>
          </div>
        </div>
        {sessionId && (
          <p className="mt-3 text-sm text-blue-700 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
            Sessão #{sessionId} ativa
          </p>
        )}
      </div>

      {error && <p className="alert-error">{error}</p>}

      {/* Text degradation */}
      <div className="card">
        <h2 className="section-title">Texto de Referência</h2>
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <label className="label">Texto original</label>
            <textarea
              value={originalText}
              onChange={(e) => setOriginalText(e.target.value)}
              placeholder="Cole o parágrafo que vai treinar…"
              rows={7}
              className="input resize-y font-mono text-xs"
            />
            <button
              onClick={handleDegrade}
              disabled={!originalText.trim() || degradeLoading}
              className="btn-secondary mt-2"
            >
              {degradeLoading ? 'Processando…' : 'Aplicar Degradação'}
            </button>
          </div>

          <div>
            <label className="label">
              Texto degradado — Nível {level}: {LEVEL_LABEL[level]}
            </label>
            {degraded ? (
              level === 4 ? (
                <div className="flex items-center justify-center h-32 bg-gray-900 rounded-lg text-gray-400 text-sm">
                  Tela em branco — tente sem apoio visual.
                </div>
              ) : (
                <pre className="bg-gray-50 border rounded-lg px-4 py-3 text-xs font-mono whitespace-pre-wrap min-h-[7rem]">
                  {degraded.text}
                </pre>
              )
            ) : (
              <div className="flex items-center justify-center h-32 bg-gray-50 border border-dashed rounded-lg text-gray-400 text-sm">
                Cole o texto e clique em «Aplicar Degradação»
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Attempt recording */}
      <div className="card">
        <h2 className="section-title">Gravar Tentativa</h2>
        <p className="text-sm text-gray-500 mb-4">
          Fale o trecho de memória. Não leia enquanto grava.
        </p>

        {!sessionId && (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 mb-4">
            Crie uma sessão primeiro.
          </p>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <label className="label">Microfone</label>
            <AudioRecorder
              onRecordingComplete={(blob, mime) => setAttemptAudio({ blob, mime })}
              disabled={!sessionId}
            />
          </div>
          <div>
            <label className="label">Ou enviar arquivo</label>
            <input
              type="file"
              accept=".wav,.mp3,.m4a,.webm,.ogg"
              disabled={!sessionId}
              onChange={handleAttemptFileUpload}
              className="text-sm text-gray-600 file:btn-secondary file:mr-3 file:cursor-pointer disabled:opacity-50"
            />
            {attemptAudio && (
              <p className="text-xs text-gray-500 mt-1">
                Áudio pronto ({(attemptAudio.blob.size / 1024).toFixed(0)} KB)
              </p>
            )}
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={!sessionId || !attemptAudio || attemptLoading}
          className="btn-primary mt-4"
        >
          {attemptLoading ? 'Analisando…' : 'Analisar Tentativa'}
        </button>
      </div>

      {/* Results */}
      {attemptResult && (
        <div className="card">
          <h2 className="section-title">Resultado</h2>

          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { label: 'Erros', value: attemptResult.error_count },
              { label: 'Hesitações', value: attemptResult.hesitation_count },
              {
                label: 'Taxa de erro',
                value: `${(attemptResult.error_ratio * 100).toFixed(0)}%`,
              },
            ].map(({ label, value }) => (
              <div key={label} className="text-center bg-gray-50 border rounded-lg py-4">
                <p className="text-2xl font-bold text-gray-900">{value}</p>
                <p className="text-xs text-gray-500 mt-1">{label}</p>
              </div>
            ))}
          </div>

          <h3 className="text-sm font-medium text-gray-700 mb-2">Análise palavra a palavra</h3>
          <DiffView
            transcript={attemptResult.transcript}
            omitted={attemptResult.omitted}
            substituted={attemptResult.substituted}
          />

          <div className="mt-4 space-y-2 text-sm">
            {attemptResult.omitted.length > 0 && (
              <p>
                <span className="font-medium text-red-700">Omitidas:</span>{' '}
                <span className="font-mono">{attemptResult.omitted.join(', ')}</span>
              </p>
            )}
            {attemptResult.substituted.length > 0 && (
              <p>
                <span className="font-medium text-orange-700">Substituições:</span>{' '}
                {attemptResult.substituted.map(([o, e]) => (
                  <span key={o} className="font-mono mr-2">
                    {o} → {e}
                  </span>
                ))}
              </p>
            )}
            {attemptResult.hesitation_points.length > 0 && (
              <p>
                <span className="font-medium text-gray-700">Hesitações:</span>{' '}
                <span className="font-mono">
                  {attemptResult.hesitation_points.map((p) => `${p.toFixed(1)}s`).join(', ')}
                </span>
              </p>
            )}
          </div>
        </div>
      )}

      {/* Schedule */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-title mb-0">Agenda de Repetição</h2>
          <button
            onClick={handleSchedule}
            disabled={scheduleLoading}
            className="btn-secondary text-xs"
          >
            {scheduleLoading ? 'Carregando…' : 'Atualizar'}
          </button>
        </div>

        {schedule ? (
          <>
            <div className="grid grid-cols-3 gap-4 mb-6">
              {[
                { label: 'Total', value: schedule.summary.total_segments },
                { label: 'Dominados', value: schedule.summary.dominated },
                { label: '% dominado', value: `${schedule.summary.pct_dominated}%` },
              ].map(({ label, value }) => (
                <div key={label} className="text-center bg-gray-50 border rounded-lg py-3">
                  <p className="text-xl font-bold text-gray-900">{value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            {schedule.repeat_segments.length > 0 ? (
              <>
                <p className="text-sm text-amber-700 mb-3">
                  {schedule.repeat_segments.length} segmento(s) para revisar:
                </p>
                <HeatMap segments={schedule.repeat_segments} />
              </>
            ) : (
              <p className="alert-success">Todos os segmentos dominados!</p>
            )}
          </>
        ) : (
          <p className="text-sm text-gray-400">
            Clique em «Atualizar» para ver quais segmentos precisam de revisão.
          </p>
        )}
      </div>
    </div>
  )
}
