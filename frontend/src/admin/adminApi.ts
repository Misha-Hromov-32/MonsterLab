import { reactive } from 'vue'
import { ApiError, jsonBody, request } from '../api'
import type { AdminSettings, Example, ExpertSettings, Landing } from '../lib/types'

// Токен в localStorage: сайт не встраивает чужих скриптов, а токен живёт неделю и
// обнуляется сменой пароля. Для httpOnly-cookie понадобился бы CSRF-токен — не стоит того.
const STORAGE_KEY = 'ml.admin.token'

export const auth = reactive({ token: readToken() })

function readToken() {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setToken(token: string) {
  auth.token = token
  try {
    if (token) localStorage.setItem(STORAGE_KEY, token)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* приватный режим — токен живёт до перезагрузки */
  }
}

async function call<T>(url: string, init: RequestInit = {}, timeoutMs = 60_000): Promise<T> {
  try {
    const headers = { ...init.headers, Authorization: `Bearer ${auth.token}` }
    return await request<T>(url, { ...init, headers }, { timeoutMs })
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) setToken('')
    throw e
  }
}

export type CheckResult = { model: string; ok: boolean; message: string }

export const adminApi = {
  login: (password: string) => request<{ token: string }>('/api/admin/login', jsonBody('POST', { password })),
  settings: () => call<AdminSettings>('/api/admin/settings'),
  saveLanding: (landing: Landing) => call<{ ok: true }>('/api/admin/landing', jsonBody('PUT', landing)),
  saveExpert: (body: { api_key?: string | null; base_url: string; models: string[] }) =>
    call<ExpertSettings>('/api/admin/expert', jsonBody('PUT', body)),
  checkExpert: () => call<{ results: CheckResult[] }>('/api/admin/expert/check', { method: 'POST' }, 90_000),

  createExample: (title: string) => call<Example>('/api/admin/examples', jsonBody('POST', { title })),
  saveExample: ({ id, title, description, context, published, hero }: Example) =>
    call<Example>(`/api/admin/examples/${id}`, jsonBody('PUT', { title, description, context, published, hero })),
  deleteExample: (id: string) => call<{ ok: true }>(`/api/admin/examples/${id}`, { method: 'DELETE' }),
  orderExamples: (ids: string[]) => call<{ ok: true }>('/api/admin/examples-order', jsonBody('PUT', { ids })),

  upload(id: string, role: 'variants' | 'competitors', files: File[]) {
    const fd = new FormData()
    fd.append('role', role)
    files.forEach((f) => fd.append('files', f))
    return call<Example>(`/api/admin/examples/${id}/images`, { method: 'POST', body: fd }, 300_000)
  },
  renameImage: (id: string, imageId: string, title: string) =>
    call<Example>(`/api/admin/examples/${id}/images/${imageId}`, jsonBody('PATCH', { title })),
  deleteImage: (id: string, imageId: string) =>
    call<Example>(`/api/admin/examples/${id}/images/${imageId}`, { method: 'DELETE' }),
  orderImages: (id: string, role: string, ids: string[]) =>
    call<Example>(`/api/admin/examples/${id}/images-order`, jsonBody('PUT', { role, ids })),
}
