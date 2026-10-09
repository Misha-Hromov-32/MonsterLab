import { beforeEach, describe, expect, it, vi } from 'vitest'

// модули читают согласие при импорте — каждый тест импортирует их заново
async function load(choice: '' | 'all' | 'necessary') {
  vi.resetModules()
  localStorage.clear()
  if (choice) localStorage.setItem('ml.cookies', JSON.stringify({ choice }))
  delete window.ym
  document.head.querySelectorAll('script[src*="mc.yandex.ru"]').forEach((s) => s.remove())
  return {
    consent: await import('./consent'),
    metrika: await import('./metrika'),
  }
}

const tagScripts = () => document.head.querySelectorAll('script[src*="mc.yandex.ru/metrika/tag.js"]').length

describe('Яндекс Метрика и согласие на cookie', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('без выбора — плашка открыта, Метрика не загружается и цели не уходят', async () => {
    const { consent, metrika } = await load('')
    expect(consent.consent.open).toBe(true)
    metrika.initMetrika(113591483)
    metrika.goal('register')
    expect(tagScripts()).toBe(0)
    expect(window.ym).toBeUndefined()
  })

  it('«Только необходимые» — Метрика не загружается', async () => {
    const { metrika } = await load('necessary')
    metrika.initMetrika(113591483)
    expect(tagScripts()).toBe(0)
  })

  it('«Принять» — загружается один раз, цели и просмотры уходят в очередь', async () => {
    const { consent, metrika } = await load('')
    consent.setConsent('all')
    expect(consent.consent.open).toBe(false)
    expect(JSON.parse(localStorage.getItem('ml.cookies')!).choice).toBe('all')
    metrika.initMetrika(113591483)
    metrika.initMetrika(113591483)
    expect(tagScripts()).toBe(1)
    metrika.goal('payment', { order_price: 990, currency: 'RUB' })
    metrika.hit('/#analyze')
    const calls = window.ym!.a as unknown[][]
    expect(calls[0].slice(0, 2)).toEqual([113591483, 'init'])
    expect(calls).toContainEqual([113591483, 'reachGoal', 'payment', { order_price: 990, currency: 'RUB' }])
    expect(calls.some((c) => c[1] === 'hit' && c[2] === '/#analyze')).toBe(true)
  })

  it('без номера счётчика ничего не грузится даже с согласием', async () => {
    const { metrika } = await load('all')
    metrika.initMetrika(null)
    expect(tagScripts()).toBe(0)
  })

  it('старая отметка «ознакомлен» не считается согласием на аналитику', async () => {
    vi.resetModules()
    localStorage.setItem('ml.cookies', '2026-10-05T10:00:00.000Z')
    const { consent } = await import('./consent')
    expect(consent.choice).toBe('')
    expect(consent.open).toBe(true)
  })
})
