interface Props {
  transcript: string
  omitted: string[]
  substituted: [string, string][]
}

export default function DiffView({ transcript, omitted, substituted }: Props) {
  if (!omitted.length && !substituted.length) {
    return (
      <p className="text-green-700 font-medium bg-green-50 border border-green-200 rounded-lg px-4 py-3">
        Nenhum erro detectado.
      </p>
    )
  }

  const subMap = new Map(substituted)
  const words = transcript.split(/\s+/).filter(Boolean)

  return (
    <p className="leading-9 font-mono text-sm bg-gray-50 border rounded-lg px-4 py-3">
      {words.map((word, i) => {
        const clean = word.toLowerCase().replace(/[.,;:!?]+$/g, '')
        if (omitted.includes(clean)) {
          return (
            <span
              key={i}
              className="line-through text-red-600 bg-red-50 border border-red-200 px-1 rounded mx-0.5"
            >
              {word}
            </span>
          )
        }
        if (subMap.has(clean)) {
          return (
            <span
              key={i}
              className="text-orange-700 font-bold bg-orange-50 border border-orange-200 px-1 rounded mx-0.5"
              title={`correto: ${subMap.get(clean)}`}
            >
              {word}
              <span className="text-xs font-normal ml-1 text-orange-500">
                [{subMap.get(clean)}]
              </span>
            </span>
          )
        }
        return (
          <span key={i} className="text-green-700 mx-0.5">
            {word}
          </span>
        )
      })}
    </p>
  )
}
