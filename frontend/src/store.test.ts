import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Analysis, CompareResult, Critique, Example, ShelfResult, User } from './lib/types'

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
  register: vi.fn(),
  login: vi.fn(),
  me: vi.fn(),
  billingPlan: vi.fn(),
  checkout: vi.fn(),
  improve: vi.fn(),
  competitors: vi.fn(),
}))
vi.mock('./api', async (importOriginal) => ({ ...(await importOriginal<typeof import('./api')>()), api }))

type Store = typeof import('./store')
type ApiModule = typeof import('./api')
type AccountModule = typeof import('./lib/account')

let store: Store
let ApiError: ApiModule['ApiError']
let acc: AccountModule

const user: User = {
  email: 'seller@example.ru',
  plan: 'free',
  pro_until: null,
  usage: { expert: 0, improve: 0, competitors: 0 },
  limits: { expert: 3, improve: 1, competitors: 3 },
}

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
  // по умолчанию покупатель вошёл: платные функции доходят до сервера
  localStorage.setItem('ml.user.token', 'u1.test')
  api.me.mockResolvedValue(user)
  vi.resetModules()
  store = await import('./store')
  ApiError = (await import('./api')).ApiError
  acc = await import('./lib/account')
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

describe('платные функции', () => {
  it('без входа разбор не уходит на сервер, а открывает вход; после входа запускается сам', async () => {
    const { setUserToken } = await import('./lib/session')
    setUserToken('')
    await twoReady()
    const v = store.state.variants[0]

    await store.runCritique(v)
    expect(api.critique).not.toHaveBeenCalled()
    expect(acc.account.dialog).toBe('login')

    api.login.mockResolvedValueOnce({ token: 'u1.new', user })
    api.critique.mockResolvedValueOnce({ models: [], errors: [], scores: {}, price_guess: null, opinions: [] })
    expect(await acc.signIn('login', user.email, 'password1')).toBe('')
    await flush()

    expect(acc.account.dialog).toBe('')
    expect(localStorage.getItem('ml.user.token')).toBe('u1.new')
    expect(api.critique).toHaveBeenCalledTimes(1)
    expect(v.critiqueStatus).toBe('ready')
  })

  it('login_required от сервера сбрасывает устаревший вход и открывает окно входа', async () => {
    await twoReady()
    api.compare.mockRejectedValueOnce(new ApiError('Войдите, чтобы пользоваться этой функцией', 'login_required', 401))

    await store.runCompare()

    expect(acc.account.dialog).toBe('login')
    expect(acc.account.reason).toMatch(/Войдите/)
    expect(localStorage.getItem('ml.user.token')).toBeNull()
    expect(store.state.compareStatus).toBe('error')
  })

  it('limit_reached показывает причину и предлагает тарифы', async () => {
    await twoReady()
    api.billingPlan.mockResolvedValue({ enabled: true, price_rub: 990, period_days: 30, limits: {} })
    const msg = 'На сегодня исчерпан лимит экспертных разборов: 3. Подписка увеличит лимит.'
    api.critique.mockRejectedValueOnce(new ApiError(msg, 'limit_reached', 403))
    const v = store.state.variants[0]

    await store.runCritique(v)

    expect(v.critiqueStatus).toBe('error')
    expect(v.critiqueError).toBe(msg)
    expect(acc.account.dialog).toBe('tariffs')
    expect(acc.account.reason).toBe(msg)
    // вход при этом остаётся
    expect(localStorage.getItem('ml.user.token')).toBe('u1.test')
  })

  it('после успешного платного запуска обновляет расход лимитов', async () => {
    await twoReady()
    api.compare.mockResolvedValueOnce(compareResult)
    api.me.mockResolvedValueOnce({ ...user, usage: { expert: 1, improve: 0, competitors: 0 } })

    await store.runCompare()
    await flush()

    expect(acc.account.user?.usage.expert).toBe(1)
  })
})

describe('улучшенная обложка', () => {
  const IMAGE = 'data:image/jpeg;base64,' + btoa('jpeg-bytes')

  it('передаёт замечания экспертов без повторов и сохраняет картинку', async () => {
    await twoReady()
    const v = store.state.variants[0]
    const issue = { severity: 'high' as const, problem: 'Мелкий текст', fix: 'Увеличить шрифт' }
    v.critique = {
      opinions: [
        { model: 'm1', issues: [issue] },
        { model: 'm2', issues: [issue] },
      ],
    } as Critique
    api.improve.mockResolvedValueOnce({ image: IMAGE })

    await store.runImprove(v)

    expect(api.improve).toHaveBeenCalledWith('a1', store.state.context, ['Мелкий текст — Увеличить шрифт'])
    expect(v.improveStatus).toBe('ready')
    expect(v.improved).toBe(IMAGE)
  })

  it('замена варианта во время генерации отбрасывает запоздавший результат', async () => {
    await twoReady()
    const v = store.state.variants[0]
    const gen = deferred<{ image: string }>()
    api.improve.mockReturnValueOnce(gen.promise)
    api.analyze.mockReturnValue(new Promise(() => {}))

    const run = store.runImprove(v)
    expect(v.improveStatus).toBe('loading')
    store.addFiles([img('other.png')], 'A')
    gen.resolve({ image: IMAGE })
    await run

    expect(v.name).toBe('other.png')
    expect(v.improved).toBeUndefined()
    expect(v.improveStatus).toBe('idle')
  })

  it('«Добавить как вариант» кладёт картинку в свободный слот под понятным именем', async () => {
    await twoReady()
    const v = store.state.variants[0]
    api.improve.mockResolvedValueOnce({ image: IMAGE })
    await store.runImprove(v)
    api.analyze.mockReturnValue(new Promise(() => {}))

    store.addImproved(v)

    const added = store.state.variants.find((x) => x.key === 'C')
    expect(added?.name).toBe('a — улучшенная.jpg')
    expect(added?.file.type).toBe('image/jpeg')
    expect(added?.status).toBe('loading')
  })
})

describe('подбор конкурентов', () => {
  it('скачивает обложки из выдачи и добавляет их в конкуренты', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, blob: async () => new Blob(['x'], { type: 'image/jpeg' }) }))
    vi.stubGlobal('fetch', fetchMock)
    api.competitors.mockResolvedValueOnce({
      query: 'термокружка',
      items: [
        { id: '101', brand: 'Brand', name: 'Кружка', url: '/api/competitors/files/k/101.jpg' },
        { id: '102', brand: '', name: 'Кружка 2', url: '/api/competitors/files/k/102.jpg' },
      ],
    })

    await store.searchCompetitors('  термокружка ')

    expect(api.competitors).toHaveBeenCalledWith('термокружка', 8)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(store.state.competitors.map((c) => c.file.name)).toEqual(['Brand 101.jpg', 'Конкурент 102.jpg'])
    expect(store.state.competitorSearch.status).toBe('ready')
  })

  it('берёт не больше, чем осталось места', async () => {
    const { MAX_COMPETITORS } = await import('./lib/constants')
    store.addCompetitors(Array.from({ length: MAX_COMPETITORS - 3 }, (_, i) => img(`r${i}.png`)))
    api.competitors.mockResolvedValueOnce({ query: 'сок', items: [] })

    await store.searchCompetitors('сок')

    expect(api.competitors).toHaveBeenCalledWith('сок', 3)
    expect(store.state.competitorSearch.status).toBe('error')
  })

  it('ошибка сервиса выдачи показывается у поиска', async () => {
    api.competitors.mockRejectedValueOnce(new ApiError('Маркетплейс не ответил', 'marketplace_failed', 502))

    await store.searchCompetitors('сок')

    expect(store.state.competitorSearch).toEqual({ status: 'error', error: 'Маркетплейс не ответил' })
    expect(store.state.competitors).toHaveLength(0)
  })
})

describe('возврат с оплаты', () => {
  it('ждёт, пока тариф станет Pro, и убирает метку из адреса', async () => {
    history.replaceState(null, '', '/?payment=return')
    api.me
      .mockResolvedValueOnce(user)
      .mockResolvedValueOnce({ ...user, plan: 'pro', pro_until: Date.UTC(2026, 9, 25, 12) / 1000 })
    const notify = vi.fn()

    await acc.checkPaymentReturn(notify, async () => {})

    expect(api.me).toHaveBeenCalledTimes(2)
    expect(notify).toHaveBeenCalledWith('Подписка активна до 25 октября 2026')
    expect(location.search).toBe('')
  })
})
