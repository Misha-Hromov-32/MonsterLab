import { authHeader } from './lib/session'
import { forgetJob, trackJob } from './lib/queue'
import type {
  Analysis,
  SavedCover,
  SavedCoverDetail,
  Billing,
  CompareResult,
  CompetitorSearch,
  Consent,
  Critique,
  ExampleResults,
  Health,
  Job,
  Legal,
  Layout,
  Showcase,
  ShelfResult,
  Site,
  Registered,
  Session,
  User,
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
    let message = 'Не удалось выполнить запрос. Попробуйте ещё раз.'
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
  if (res.status === 202) {
    // тяжёлая работа поставлена в очередь — ждём её здесь, вызывающему коду это незаметно
    const body = await res.json()
    return (body?.job ? waitJob<T>(body.job, signal) : body) as T
  }
  return res.json() as Promise<T>
}

const JOB_POLL_S = 10 // сервер отвечает, как только задача сдвинулась или завершилась
const JOB_MAX_MS = 20 * 60_000
const JOB_RETRIES = 4

/** Ждёт задачу очереди: место и оценку времени показывает плашка (lib/queue.ts), потом — результат. */
async function waitJob<T>(first: Job, signal?: AbortSignal): Promise<T> {
  let job = first
  const started = Date.now()
  let failures = 0
  trackJob(job)
  try {
    while (job.status === 'queued' || job.status === 'running') {
      if (Date.now() - started > JOB_MAX_MS) throw new ApiError('Очередь слишком длинная. Попробуйте позже.', 'timeout')
      try {
        job = (
          await request<{ job: Job }>(`/api/jobs/${job.id}?wait=${JOB_POLL_S}`, withAuth(), {
            timeoutMs: (JOB_POLL_S + 20) * 1000,
            signal,
          })
        ).job
        failures = 0
        trackJob(job)
      } catch (e) {
        // короткий обрыв связи не должен терять задачу — повторяем опрос
        if (!(e instanceof ApiError) || !['network', 'timeout'].includes(e.code) || ++failures > JOB_RETRIES) throw e
        await new Promise((r) => setTimeout(r, 1500 * failures))
      }
    }
  } catch (e) {
    if (e instanceof ApiError && e.code === 'aborted')
      // картинку заменили, пока задача ждала, — снимаем её, чтобы не занимала очередь
      void fetch(`/api/jobs/${job.id}`, withAuth({ method: 'DELETE' })).catch(() => {})
    throw e
  } finally {
    forgetJob(job.id)
  }
  if (job.status === 'done') return job.result as T
  const err = job.error
  throw new ApiError(
    err?.message ?? 'Не удалось выполнить задачу. Попробуйте ещё раз.',
    err?.code ?? 'error',
    err?.status ?? 0,
  )
}

export const jsonBody = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

/** Запрос покупателя: добавляет токен входа. Админские запросы сюда не ходят — у них свой токен. */
export const withAuth = (init: RequestInit = {}): RequestInit => ({
  ...init,
  headers: { ...init.headers, ...authHeader() },
})

export const api = {
  library: (offset = 0) => request<{ items: SavedCover[]; total: number }>(`/api/library?offset=${offset}`, withAuth()),
  savedCover: (id: string) => request<SavedCoverDetail>(`/api/library/${encodeURIComponent(id)}`, withAuth()),
  deleteCover: (id: string) =>
    request<{ ok: boolean }>(`/api/library/${encodeURIComponent(id)}`, withAuth({ method: 'DELETE' })),
  health: () => request<Health>('/api/health', {}, { timeoutMs: 10_000 }),
  /** preview — главная в iframe админки: такой показ не считается визитом */
  site: (preview = false) =>
    request<Site>(`/api/public/site${preview ? '?preview=true' : ''}`, {}, { timeoutMs: 10_000 }),
  legal: () => request<Legal>('/api/public/legal', {}, { timeoutMs: 10_000 }),
  showcase: () => request<Showcase | null>('/api/public/showcase'),
  exampleResults: (id: string) =>
    request<ExampleResults>(`/api/public/examples/${id}/results`, {}, { timeoutMs: 30_000 }),

  analyze(file: File, signal?: AbortSignal) {
    const fd = new FormData()
    fd.append('file', file)
    return request<Analysis>('/api/analyze', withAuth({ method: 'POST', body: fd }), { timeoutMs: 120_000, signal })
  },

  shelf(variants: Record<string, string>, competitors: File[], layout: Layout) {
    const fd = new FormData()
    fd.append('variants', JSON.stringify(variants))
    fd.append('layout', layout)
    competitors.forEach((f) => fd.append('competitors', f))
    return request<ShelfResult>('/api/shelf', withAuth({ method: 'POST', body: fd }), { timeoutMs: 600_000 })
  },

  /** визуальный разбор; competitors — обложки конкурентов с полки, чтобы оценить обложку рядом с ними */
  critique(id: string, context: object, competitors: File[] = []) {
    const fd = new FormData()
    fd.append('id', id)
    fd.append('context', JSON.stringify(context))
    competitors.forEach((f) => fd.append('competitors', f))
    return request<Critique>('/api/expert/critique', withAuth({ method: 'POST', body: fd }), { timeoutMs: 300_000 })
  },

  compare: (variants: Record<string, string>, context: object) =>
    request<CompareResult>('/api/expert/compare', withAuth(jsonBody('POST', { variants, context })), {
      timeoutMs: 300_000,
    }),

  // ---------------------------------------------------------- аккаунт, подписка, платные инструменты

  // письмо уходит прямо во время запроса — даём почтовому серверу время ответить
  /** галочки согласий обязательны: без них сервер аккаунт не создаёт */
  register: (email: string, password: string, consent: Consent) =>
    request<Registered>(
      '/api/auth/register',
      jsonBody('POST', {
        email,
        password,
        accept_terms: consent.terms,
        accept_personal_data: consent.personalData,
      }),
      { timeoutMs: 40_000 },
    ),
  login: (email: string, password: string) =>
    request<Session>('/api/auth/login', jsonBody('POST', { email, password }), { timeoutMs: 20_000 }),
  resend: (email: string) =>
    request<{ ok: true }>('/api/auth/resend', jsonBody('POST', { email }), { timeoutMs: 40_000 }),
  verify: (token: string) => request<Session>('/api/auth/verify', jsonBody('POST', { token }), { timeoutMs: 20_000 }),
  forgot: (email: string) =>
    request<{ ok: true }>('/api/auth/forgot', jsonBody('POST', { email }), { timeoutMs: 40_000 }),
  resetPassword: (token: string, password: string) =>
    request<Session>('/api/auth/reset', jsonBody('POST', { token, password }), { timeoutMs: 20_000 }),
  me: () => request<User>('/api/auth/me', withAuth(), { timeoutMs: 15_000 }),

  billingPlans: () => request<Billing>('/api/billing/plans', {}, { timeoutMs: 15_000 }),
  checkout: (plan: string) =>
    request<{ url: string }>('/api/billing/checkout', withAuth(jsonBody('POST', { plan })), { timeoutMs: 30_000 }),

  /** улучшенная обложка рисуется 30–60 секунд */
  improve: (id: string, context: object, issues: string[]) =>
    request<{ image: string }>('/api/improve', withAuth(jsonBody('POST', { id, context, issues })), {
      timeoutMs: 300_000,
    }),

  competitors: (query: string, limit: number) =>
    request<CompetitorSearch>(`/api/competitors?${new URLSearchParams({ query, limit: String(limit) })}`, withAuth(), {
      timeoutMs: 60_000,
    }),
}
