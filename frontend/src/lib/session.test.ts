import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type Session = typeof import('./session')
let s: Session

beforeEach(() => {
  localStorage.clear()
  vi.resetModules()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('токен покупателя', () => {
  it('сохраняется между перезагрузками и удаляется при выходе', async () => {
    s = await import('./session')
    expect(s.session.token).toBe('')
    s.setUserToken('u1.abc')
    expect(localStorage.getItem('ml.user.token')).toBe('u1.abc')

    vi.resetModules()
    s = await import('./session')
    expect(s.session.token).toBe('u1.abc')

    s.setUserToken('')
    expect(localStorage.getItem('ml.user.token')).toBeNull()
  })

  it('заголовок входа есть только у вошедшего покупателя', async () => {
    s = await import('./session')
    expect(s.authHeader()).toEqual({})
    s.setUserToken('u1.abc')
    expect(s.authHeader()).toEqual({ Authorization: 'Bearer u1.abc' })
  })

  it('платные запросы идут с токеном, бесплатные — без', async () => {
    localStorage.setItem('ml.user.token', 'u1.xyz')
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const { api } = await import('../api')

    await api.critique('id1', {})
    await api.competitors('сок', 5)
    await api.analyze(new File(['x'], 'a.png', { type: 'image/png' }))

    const headers = (i: number) => new Headers(fetchMock.mock.calls[i][1]?.headers)
    expect(headers(0).get('Authorization')).toBe('Bearer u1.xyz')
    expect(headers(0).get('Content-Type')).toBe('application/json')
    expect(headers(1).get('Authorization')).toBe('Bearer u1.xyz')
    expect(fetchMock.mock.calls[1][0]).toBe(`/api/competitors?${new URLSearchParams({ query: 'сок', limit: '5' })}`)
    expect(headers(2).get('Authorization')).toBeNull()
  })
})
