import type {
  Analysis,
  CompareResult,
  Critique,
  ExampleResults,
  Health,
  Layout,
  Showcase,
  ShelfResult,
  Site,
} from './lib/types'

/** Ошибка API: message — готовая фраза для пользователя, code — для логики (image_expired и т. п.). */
export class ApiError extends Error {
  constructor(
    message: string,
    public code: string = 'error',
    public status = 0,
  ) {
    super(message)
  }
}

export interface RequestOptions {
  timeoutMs?: number
  /** отмена снаружи — например, когда картинку заменили, пока шёл анализ */
  signal?: AbortSignal
}

export async function request<T>(url: string, init: RequestInit = {}, opts: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 60_000, signal } = opts
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  const onAbort = () => ctrl.abort()
  signal?.addEventListener('abort', onAbort)
  let res: Response
  try {
    res = await fetch(url, { ...init, signal: ctrl.signal })
  } catch {
    if (signal?.aborted) throw new ApiError('Запрос отменён', 'aborted')
    throw ctrl.signal.aborted
      ? new ApiError('Сервер слишком долго не отвечает. Попробуйте ещё раз.', 'timeout')
      : new ApiError('Сервис временно недоступен. Обновите страницу через минуту.', 'network')
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onAbort)
  }
  if (!res.ok) {
    let message = 'Что-то пошло не так. Попробуйте ещё раз.'
    let code = 'error'
    try {
      const detail = (await res.json()).detail
      if (detail && typeof detail === 'object') {
        message = detail.message ?? message
        code = detail.code ?? code
      } else if (typeof detail === 'string') message = detail
    } catch {
      /* тело не JSON — оставляем общее сообщение */
    }
    throw new ApiError(message, code, res.status)
  }
  return res.json() as Promise<T>
}

export const jsonBody = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => request<Health>('/api/health', {}, { timeoutMs: 10_000 }),
  site: () => request<Site>('/api/public/site', {}, { timeoutMs: 10_000 }),
  showcase: () => request<Showcase | null>('/api/public/showcase'),
  exampleResults: (id: string) =>
    request<ExampleResults>(`/api/public/examples/${id}/results`, {}, { timeoutMs: 30_000 }),

  analyze(file: File, signal?: AbortSignal) {
    const fd = new FormData()
    fd.append('file', file)
    return request<Analysis>('/api/analyze', { method: 'POST', body: fd }, { timeoutMs: 120_000, signal })
  },

  shelf(variants: Record<string, string>, competitors: File[], layout: Layout) {
    const fd = new FormData()
    fd.append('variants', JSON.stringify(variants))
    fd.append('layout', layout)
    competitors.forEach((f) => fd.append('competitors', f))
    return request<ShelfResult>('/api/shelf', { method: 'POST', body: fd }, { timeoutMs: 600_000 })
  },

  critique: (id: string, context: object) =>
    request<Critique>('/api/expert/critique', jsonBody('POST', { id, context }), { timeoutMs: 300_000 }),

  compare: (variants: Record<string, string>, context: object) =>
    request<CompareResult>('/api/expert/compare', jsonBody('POST', { variants, context }), { timeoutMs: 300_000 }),
}
