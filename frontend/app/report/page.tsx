'use client'

import { useState } from 'react'
import HeatMap from '@/components/HeatMap'
import { useApp } from '@/context/AppContext'
import { ApiError } from '@/lib/api'
import type { ReportData } from '@/lib/types'
import { downloadBlob } from '@/lib/utils'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export default function RelatorioPage() {
  const { presId } = useApp()
  const [inputPresId, setInputPresId] = useState(presId ?? 1)
  const [fmt, setFmt] = useState<'json' | 'pdf'>('json')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reportData, setReportData] = useState<ReportData | null>(null)

  async function handleGenerate() {
    setLoading(true)
    setError(null)
    setReportData(null)
    try {
      const params = new URLSearchParams({ fmt })
      const res = await fetch(`${BASE}/presentations/${inputPresId}/report?${params}`)
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        throw new ApiError(res.status, j.detail ?? res.statusText)
      }
      const blob = await res.blob()
      const filename = `relatorio_${inputPresId}.${fmt}`
      downloadBlob(blob, filename)

      if (fmt === 'json') {
        const text = await blob.text()
        setReportData(JSON.parse(text) as ReportData)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao gerar relatório.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="card">
        <h2 className="section-title">Relatório de Progresso</h2>

        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="label">Apresentação ID</label>
            <input
              type="number"
              min={1}
              value={inputPresId}
              onChange={(e) => setInputPresId(Number(e.target.value))}
              className="input w-40"
            />
          </div>

          <div>
            <label className="label">Formato</label>
            <div className="flex gap-2">
              {(['json', 'pdf'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFmt(f)}
                  className={`px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${
                    fmt === f
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <button onClick={handleGenerate} disabled={loading} className="btn-primary">
            {loading ? 'Gerando…' : `Gerar e Baixar ${fmt.toUpperCase()}`}
          </button>
        </div>

        {error && <p className="alert-error mt-4">{error}</p>}
      </div>

      {reportData && (
        <>
          <div className="card">
            <h2 className="section-title">Resumo</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Metric label="Sessões" value={reportData.sessions.length} />
              <Metric label="Segmentos" value={reportData.segments.length} />
              <Metric
                label="Dominados"
                value={reportData.segments.filter((s) => s.difficulty_score <= 0.2).length}
              />
              <Metric
                label="% dominado"
                value={
                  reportData.segments.length
                    ? `${Math.round(
                        (reportData.segments.filter((s) => s.difficulty_score <= 0.2).length /
                          reportData.segments.length) *
                          100
                      )}%`
                    : '—'
                }
              />
            </div>
          </div>

          {reportData.sessions.length > 0 && (
            <div className="card">
              <h2 className="section-title">Sessões</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="border-b text-gray-500 text-xs">
                      <th className="py-2 pr-4">ID</th>
                      <th className="py-2 pr-4">Nível</th>
                      <th className="py-2 pr-4">Iniciada</th>
                      <th className="py-2">Pontuação média</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {reportData.sessions.map((s) => (
                      <tr key={s.id}>
                        <td className="py-2 pr-4 font-mono text-gray-600">#{s.id}</td>
                        <td className="py-2 pr-4">{s.level}</td>
                        <td className="py-2 pr-4 text-gray-500">
                          {new Date(s.started_at).toLocaleString('pt-BR')}
                        </td>
                        <td className="py-2">
                          {s.mean_score !== null ? s.mean_score.toFixed(2) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card">
            <h2 className="section-title">Mapa de Calor por Segmento</h2>
            <HeatMap
              segments={reportData.segments.map((s) => ({
                index: s.index,
                score: s.difficulty_score,
                text: s.text,
              }))}
            />
          </div>
        </>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-center bg-gray-50 border rounded-lg py-4">
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  )
}
