import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request } from './api'
import { queue } from './lib/queue'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const job = (status: string, extra: object = {}) => ({
  job: { id: 'j1', lane: 'neural', title: 'Проверка обложки', status, position: 2, eta_s: 6, waited_s: 0, ...extra },
})

afterEach(() => vi.unstubAllGlobals())

describe('задачи очереди', () => {
  it('202 → опрос → результат; пока ждём, задача видна в плашке', async () => {
    const seen: string[] = []
    const fetchMock = vi.fn(async (url: string) => {
      if (url === '/api/analyze') return json(202, job('queued'))
      seen.push(queue.jobs.j1?.status ?? 'нет')
      return seen.length === 1 ? json(200, job('running')) : json(200, job('done', { result: { index: 71 } }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await request<{ index: number }>('/api/analyze', { method: 'POST' })

    expect(result).toEqual({ index: 71 })
    expect(seen).toEqual(['queued', 'running'])
    expect(fetchMock.mock.calls[1][0]).toBe('/api/jobs/j1?wait=10')
    expect(queue.jobs.j1).toBeUndefined()
  })

  it('ошибка задачи приходит как ApiError с её кодом', async () => {
    const error = { status: 404, code: 'image_expired', message: 'Изображение не найдено' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url === '/api/shelf' ? json(202, job('queued')) : json(200, job('error', { error })),
      ),
    )

    const err = (await request('/api/shelf', { method: 'POST' }).catch((e) => e)) as ApiError

    expect(err).toBeInstanceOf(ApiError)
    expect([err.code, err.status]).toEqual(['image_expired', 404])
  })
})
