import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Analysis, CompareResult, Example, ShelfResult } from './lib/types'

// Запросы к серверу подменяем; ApiError оставляем настоящим — store проверяет instanceof.
const api = vi.hoisted(() => ({
  analyze: vi.fn(),
  compare: vi.fn(),
  shelf: vi.fn(),
  critique: vi.fn(),
  health: vi.fn(),
  site: vi.fn(),
  showcase: vi.fn(),
  exampleResults: vi.fn(),
}))
vi.mock('./api', async (importOriginal) => ({ ...(await importOriginal<typeof import('./api')>()), api }))

type Store = typeof import('./store')
type ApiModule = typeof import('./api')

let store: Store
let ApiError: ApiModule['ApiError']

/** Промис, который тест разрешает сам — чтобы управлять порядком ответов. */
function deferred<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

/** Даём отработать промисам и watch-ам Vue. */
const flush = () => new Promise((r) => setTimeout(r))

const img = (name: string) => new File(['x'], name, { type: 'image/png' })
const analysis = (id: string) => ({ id }) as Analysis
const compareResult = { errors: [], ranking: [], records: [] } as CompareResult
const shelfResult = { mode: 'variants' } as ShelfResult

/** Два готовых варианта с id картинок a1 и b1. */
async function twoReady() {
  api.analyze.mockResolvedValueOnce(analysis('a1')).mockResolvedValueOnce(analysis('b1'))
  store.addFiles([img('a.png'), img('b.png')])
  await flush()
  expect(store.ready.value).toHaveLength(2)
}

beforeEach(async () => {
  Object.values(api).forEach((f) => f.mockReset())
  let n = 0
  URL.createObjectURL = vi.fn(() => `blob:${++n}`)
  URL.revokeObjectURL = vi.fn()
  localStorage.clear()
  vi.resetModules()
  store = await import('./store')
  ApiError = (await import('./api')).ApiError
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('анализ варианта', () => {
  it('поздний ответ по заменённой картинке не затирает новый анализ', async () => {
    const first = deferred<Analysis>()
    const second = deferred<Analysis>()
    api.analyze.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    store.addFiles([img('old.png')])
    store.addFiles([img('new.png')], 'A')
    expect((api.analyze.mock.calls[0][1] as AbortSignal).aborted).toBe(true)

    second.resolve(analysis('new'))
    await flush()
    first.resolve(analysis('old'))
    await flush()

    const v = store.state.variants[0]
    expect(v.name).toBe('new.png')
    expect(v.status).toBe('ready')
    expect(v.analysis?.id).toBe('new')
  })
})

describe('сравнение', () => {
  it('ответ после смены набора вариантов отбрасывается', async () => {
    await twoReady()
    const cmp = deferred<CompareResult>()
    api.compare.mockReturnValueOnce(cmp.promise)
    api.analyze.mockReturnValue(new Promise(() => {}))

    const run = store.runCompare()
    expect(store.state.compareStatus).toBe('loading')
    store.addFiles([img('c.png')])
    cmp.resolve(compareResult)
    await run

    expect(store.state.compare).toBeNull()
    expect(store.state.compareStatus).toBe('idle')
  })

  it('добавление конкурента не оставляет сравнение в «loading»', async () => {
    await twoReady()
    const cmp = deferred<CompareResult>()
    api.compare.mockReturnValueOnce(cmp.promise)

    const run = store.runCompare()
    store.addCompetitors([img('rival.png')])
    cmp.resolve(compareResult)
    await run

    expect(store.state.compareStatus).toBe('ready')
    expect(store.state.compare).toEqual(compareResult)
  })
})

describe('withIds', () => {
  it('при image_expired перезагружает картинки и повторяет запрос, не выкидывая с вкладки сравнения', async () => {
    await twoReady()
    store.state.view = 'compare'
    await flush()

    const reA = deferred<Analysis>()
    const reB = deferred<Analysis>()
    api.analyze.mockReturnValueOnce(reA.promise).mockReturnValueOnce(reB.promise)
    api.compare
      .mockRejectedValueOnce(new ApiError('Картинка устарела', 'image_expired', 410))
      .mockResolvedValueOnce(compareResult)

    const run = store.runCompare()
    await flush()
    // картинки перезагружаются — вкладка сравнения остаётся открытой
    expect(api.analyze).toHaveBeenCalledTimes(4)
    expect(store.state.view).toBe('compare')

    reA.resolve(analysis('a2'))
    reB.resolve(analysis('b2'))
    await run

    expect(api.compare).toHaveBeenCalledTimes(2)
    expect(api.compare.mock.calls[0][0]).toEqual({ A: 'a1', B: 'b1' })
    expect(api.compare.mock.calls[1][0]).toEqual({ A: 'a2', B: 'b2' })
    expect(store.state.compareStatus).toBe('ready')
    expect(store.state.view).toBe('compare')
  })

  it('повторяет только один раз', async () => {
    await twoReady()
    api.analyze.mockResolvedValueOnce(analysis('a2')).mockResolvedValueOnce(analysis('b2'))
    const expired = () => new ApiError('Картинка устарела', 'image_expired', 410)
    api.compare.mockRejectedValueOnce(expired()).mockRejectedValueOnce(expired())
    vi.spyOn(console, 'warn').mockImplementation(() => {})

    await store.runCompare()

    expect(api.compare).toHaveBeenCalledTimes(2)
    expect(store.state.compareStatus).toBe('error')
  })
})

describe('конкуренты', () => {
  it('попытка добавить сверх лимита не стирает результат полки', async () => {
    const { MAX_COMPETITORS } = await import('./lib/constants')
    await twoReady()
    store.addCompetitors(Array.from({ length: MAX_COMPETITORS }, (_, i) => img(`r${i}.png`)))
    api.shelf.mockResolvedValueOnce(shelfResult)
    await store.runShelf()
    expect(store.state.shelfStatus).toBe('ready')

    store.addCompetitors([img('extra.png')])

    expect(store.state.competitors).toHaveLength(MAX_COMPETITORS)
    expect(store.state.shelf).toEqual(shelfResult)
    expect(store.state.shelfStatus).toBe('ready')
    expect(store.state.toast).toMatch(/Уже добавлено/)
  })
})

describe('примеры', () => {
  it('двойное нажатие не дублирует варианты и конкурентов', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, blob: async () => new Blob(['x'], { type: 'image/jpeg' }) })),
    )
    api.analyze.mockReturnValue(new Promise(() => {}))
    api.exampleResults.mockResolvedValue({ ready: false })
    const image = (id: string) => ({ id, title: id, width: 1, height: 1, url: `/img/${id}` })
    const ex: Example = {
      id: 'ex',
      title: 'Пример',
      description: '',
      context: { query: 'сок', category: '', price: '', audience: '' },
      variants: [image('v1'), image('v2')],
      competitors: [image('c1')],
    }

    await Promise.all([store.loadExample(ex), store.loadExample(ex)])

    expect(store.state.variants.map((v) => v.key)).toEqual(['A', 'B'])
    expect(store.state.competitors).toHaveLength(1)
    expect(store.state.context.query).toBe('сок')
  })

  it('готовые результаты: обложки не уходят на анализ, полка открывается без расчёта', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, blob: async () => new Blob(['x'], { type: 'image/jpeg' }) })),
    )
    const image = (id: string) => ({ id, title: id, width: 1, height: 1, url: `/img/${id}` })
    const ex: Example = {
      id: 'ex',
      title: 'Пример',
      description: '',
      context: { query: '', category: '', price: '', audience: '' },
      variants: [image('v1'), image('v2')],
      competitors: [image('c1')],
    }
    const shelfMobile = { mode: 'competitors' } as ShelfResult
    api.exampleResults.mockResolvedValue({
      ready: true,
      keys: { A: 'v1', B: 'v2' },
      variants: { v1: analysis('u1'), v2: analysis('u2') },
      shelf: { mobile: shelfMobile },
    })

    await store.loadExample(ex)
    expect(api.analyze).not.toHaveBeenCalled()
    expect(store.state.variants.map((v) => [v.status, v.analysis?.id])).toEqual([
      ['ready', 'u1'],
      ['ready', 'u2'],
    ])

    await store.runShelf()
    expect(api.shelf).not.toHaveBeenCalled()
    expect(store.state.shelf).toStrictEqual(shelfMobile)

    // после изменения набора готовый результат больше не подходит — считаем заново
    store.removeCompetitor(0)
    api.shelf.mockResolvedValue(shelfMobile)
    await store.runShelf()
    expect(api.shelf).toHaveBeenCalledTimes(1)
  })
})
