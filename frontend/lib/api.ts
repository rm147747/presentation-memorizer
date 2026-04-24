const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(method: string, path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method, ...init })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const json = await res.json()
      detail = json.detail ?? detail
    } catch { /* non-JSON body */ }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  post: <T>(path: string, body: unknown) =>
    request<T>('POST', path, {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  postForm: <T>(path: string, form: FormData, params?: Record<string, string>) => {
    const url = params ? `${path}?${new URLSearchParams(params)}` : path
    return request<T>('POST', url, { body: form })
  },

  get: <T>(path: string, params?: Record<string, string>) => {
    const url = params ? `${path}?${new URLSearchParams(params)}` : path
    return request<T>('GET', url)
  },

  getRaw: async (path: string, params?: Record<string, string>): Promise<Blob> => {
    const url = params ? `${path}?${new URLSearchParams(params)}` : path
    const res = await fetch(`${BASE}${url}`)
    if (!res.ok) throw new ApiError(res.status, res.statusText)
    return res.blob()
  },
}
