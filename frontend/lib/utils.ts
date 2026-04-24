export function scoreColor(score: number): string {
  if (score <= 0.2) return 'bg-green-100 text-green-800 border-green-200'
  if (score <= 0.5) return 'bg-yellow-100 text-yellow-800 border-yellow-200'
  return 'bg-red-100 text-red-800 border-red-200'
}

export function scoreBarColor(score: number): string {
  if (score <= 0.2) return 'bg-green-500'
  if (score <= 0.5) return 'bg-yellow-400'
  return 'bg-red-500'
}

export function scoreLabel(score: number): string {
  if (score <= 0.2) return 'dominado'
  if (score <= 0.5) return 'instável'
  return 'crítico'
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
