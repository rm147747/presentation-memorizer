import { scoreBarColor, scoreColor, scoreLabel } from '@/lib/utils'

interface Segment {
  index: number
  score: number
  text: string
}

interface Props {
  segments: Segment[]
}

export default function HeatMap({ segments }: Props) {
  if (!segments.length) {
    return <p className="text-gray-500 text-sm">Nenhum segmento para exibir.</p>
  }

  return (
    <div className="space-y-3">
      {segments.map((seg) => (
        <div key={seg.index} className="flex items-start gap-3">
          <span
            className={`text-xs font-mono px-2 py-0.5 rounded-full border shrink-0 mt-0.5 ${scoreColor(seg.score)}`}
          >
            #{seg.index} · {scoreLabel(seg.score)}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-700 truncate">{seg.text}</p>
            <div className="mt-1.5 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${scoreBarColor(seg.score)}`}
                style={{ width: `${Math.min(seg.score * 100, 100)}%` }}
              />
            </div>
          </div>
          <span className="text-xs text-gray-400 font-mono shrink-0 mt-0.5">
            {seg.score.toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  )
}
