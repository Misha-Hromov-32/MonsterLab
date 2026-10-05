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
  resend: vi.fn(),
  verify: vi.fn(),
  forgot: vi.fn(),
  resetPassword: vi.fn(),
  me: vi.fn(),
  billingPlans: vi.fn(),
  checkout: vi.fn(),
  oauthStart: vi.fn(),
  oauthFinish: vi.fn(),
  checkPayment: vi.fn(async () => ({ activated: false, user: null })),
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
  plan: 'demo',
  plan_title: 'Демо',
  pro_until: null,
  usage: { analyze: 0, shelf: 0, expert: 0, choice: 0, improve: 0, competitors: 0 },
  limits: { analyze: 10, shelf: 3, expert: 2, choice: 1, improve: 1, competitors: 2 },
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

describe('данные о товаре', () => {
  it('не восстанавливает старый товар из браузера', async () => {
    localStorage.setItem('ml.prefs', JSON.stringify({ context: { query: 'крем', price: '990' } }))
    vi.resetModules()
    const fresh = await import('./store')
    expect(Object.values(fresh.state.context).every((value) => value === '')).toBe(true)
    expect(JSON.parse(localStorage.getItem('ml.prefs')!).context).toBeUndefined()
  })

  it('новый анализ очищает введённые данные и не сохраняет их в браузере', async () => {
    Object.assign(store.state.context, { query: 'товар', price: '123', audience: 'моя аудитория' })
    store.state.opacity = 0.5
    await flush()
    expect(JSON.parse(localStorage.getItem('ml.prefs')!).context).toBeUndefined()
    store.resetAll()
    expect(Object.values(store.state.context).every((value) => value === '')).toBe(true)
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
    expect(store.state.context.query).toBe('')
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
    await twoReady()
    const { setUserToken } = await import('./lib/session')
    setUserToken('')
    const v = store.state.variants[0]

    await store.runCritique(v)
    expect(api.critique).not.toHaveBeenCalled()
    expect(acc.account.dialog).toBe('login')

    api.login.mockResolvedValueOnce({ token: 'u1.new', user })
    api.critique.mockResolvedValueOnce({ model: 'm', errors: [], verdict: 'ок', improvements: [] })
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
    api.billingPlans.mockResolvedValue({ enabled: true, demo: user.limits, plans: [] })
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

  it('даёт сгенерированному варианту бонус и сохраняет реальную оценку', async () => {
    await twoReady()
    const original = store.state.variants[0]
    original.analysis!.index = 65
    original.improved = IMAGE
    api.analyze.mockResolvedValueOnce({ id: 'generated', index: 40 } as Analysis)
    store.addImproved(original)
    await flush()
    const generated = store.state.variants.find((v) => v.analysis?.id === 'generated')!
    expect(generated.analysis!.index).toBe(70)
    expect(generated.measuredIndex).toBe(40)
    expect(store.generatedIndex(98, 99)).toBe(100)
    api.analyze.mockResolvedValueOnce({ id: 'normal', index: 35 } as Analysis)
    store.addFiles([img('normal.png')], generated.key)
    await flush()
    expect(generated.analysis!.index).toBe(35)
    expect(generated.measuredIndex).toBeUndefined()
  })

  it('передаёт замечания экспертов без повторов и сохраняет картинку', async () => {
    await twoReady()
    const v = store.state.variants[0]
    const issue = { priority: 1, what: 'Мелкий текст', why: 'не читается в ленте', how: 'Увеличить шрифт' }
    v.critique = { improvements: [issue, issue] } as Critique
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

describe('личный кабинет', () => {
  it('открывает сохранённый анализ без повторного запроса и сохраняет бонус генерации', () => {
    const raw = { id: 'saved', index: 40 } as Analysis
    const opened = store.openSavedCover({
      id: 'personal',
      name: 'Моя обложка',
      image: 'data:image/jpeg;base64,' + btoa('saved-bytes'),
      analysis: raw,
      generated_baseline: 65,
    })
    expect(opened).toBe(true)
    expect(api.analyze).not.toHaveBeenCalled()
    expect(store.state.variants[0].analysis!.index).toBe(70)
    expect(store.state.variants[0].measuredIndex).toBe(40)
    expect(raw.index).toBe(40)
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
  it('ждёт, пока тариф оплатится, и убирает метку из адреса', async () => {
    history.replaceState(null, '', '/?payment=return')
    api.me
      .mockResolvedValueOnce(user)
      .mockResolvedValueOnce({ ...user, plan: 'pro', plan_title: 'Про', pro_until: Date.UTC(2026, 9, 25, 12) / 1000 })
    const notify = vi.fn()

    await acc.checkPaymentReturn(notify, async () => {})

    expect(api.me).toHaveBeenCalledTimes(2)
    expect(api.checkPayment).toHaveBeenCalledTimes(2)
    expect(notify).toHaveBeenCalledWith('Тариф «Про» активен до 25 октября 2026')
    expect(location.search).toBe('')
  })

  it('неудачная оплата — сообщение и чистый адрес', async () => {
    history.replaceState(null, '', '/?payment=fail')
    const notify = vi.fn()

    await acc.checkPaymentReturn(notify, async () => {})

    expect(notify).toHaveBeenCalledWith('Оплата не прошла — попробуйте ещё раз или выберите другой способ')
    expect(location.search).toBe('')
  })
})

describe('вход через VK ID / Яндекс ID', () => {
  beforeEach(async () => {
    const { setUserToken } = await import('./lib/session')
    setUserToken('')
    acc.account.dialog = ''
  })

  it('возврат с совпадающим state — вход и чистый адрес', async () => {
    sessionStorage.setItem('ml.oauth', JSON.stringify({ provider: 'vk', state: 'st-1' }))
    history.replaceState(null, '', '/auth/vk/callback?code=c1&state=st-1&device_id=dev')
    api.oauthFinish.mockResolvedValueOnce({ token: 'u2.vk', user })
    const notify = vi.fn()

    expect(await acc.handleOAuthCallback(notify)).toBe(true)

    expect(api.oauthFinish).toHaveBeenCalledWith('vk', { code: 'c1', state: 'st-1', device_id: 'dev' })
    expect(notify).toHaveBeenCalledWith(`Вы вошли через VK ID: ${user.email}`)
    expect(location.pathname).toBe('/')
    expect(location.search).toBe('')
    expect(sessionStorage.getItem('ml.oauth')).toBeNull()
  })

  it('чужой state — на сервер не идём, предлагаем начать заново', async () => {
    sessionStorage.setItem('ml.oauth', JSON.stringify({ provider: 'vk', state: 'mine' }))
    history.replaceState(null, '', '/auth/vk/callback?code=c1&state=attacker')
    api.oauthFinish.mockClear()

    await acc.handleOAuthCallback(vi.fn())

    expect(api.oauthFinish).not.toHaveBeenCalled()
    expect(acc.account.dialog).toBe('login')
  })

  it('нового пользователя без согласий отправляет на вкладку регистрации', async () => {
    sessionStorage.setItem('ml.oauth', JSON.stringify({ provider: 'yandex', state: 's' }))
    history.replaceState(null, '', '/auth/yandex/callback?code=c&state=s')
    api.oauthFinish.mockRejectedValueOnce(new ApiError('нужно согласие', 'consent_required', 422))

    await acc.handleOAuthCallback(vi.fn())

    expect(acc.account.dialog).toBe('login')
    expect(acc.account.authMode).toBe('register')
  })

  it('обычный адрес — не возврат от провайдера', async () => {
    history.replaceState(null, '', '/')
    expect(await acc.handleOAuthCallback(vi.fn())).toBe(false)
  })
})

describe('вход и подтверждение почты', () => {
  beforeEach(async () => {
    const { setUserToken } = await import('./lib/session')
    setUserToken('')
  })

  it('без входа обложка не уходит на сервер; после входа добавляется сама', async () => {
    store.addFiles([img('a.png')])
    expect(api.analyze).not.toHaveBeenCalled()
    expect(store.state.variants).toHaveLength(0)
    expect(acc.account.dialog).toBe('login')

    api.login.mockResolvedValueOnce({ token: 'u2.new', user })
    api.analyze.mockResolvedValueOnce(analysis('a1'))
    expect(await acc.signIn('login', user.email, 'password1')).toBe('')
    await flush()
    expect(store.state.variants).toHaveLength(1)
    expect(api.analyze).toHaveBeenCalledTimes(1)
  })

  it('после регистрации и при неподтверждённой почте окно просит проверить почту', async () => {
    acc.openLogin('', undefined, 'register')
    api.register.mockResolvedValueOnce({ status: 'verify', email: 'new@example.ru' })
    expect(await acc.signIn('register', 'New@example.ru', 'password1', { terms: true, personalData: true })).toBe('')
    expect(api.register).toHaveBeenCalledWith('New@example.ru', 'password1', { terms: true, personalData: true })
    expect(acc.account.authMode).toBe('sent')
    expect(acc.account.pendingEmail).toBe('new@example.ru')
    expect(localStorage.getItem('ml.user.token')).toBeNull()

    acc.openLogin()
    api.login.mockRejectedValueOnce(new ApiError('Подтвердите почту', 'email_unverified', 403))
    expect(await acc.signIn('login', 'new@example.ru', 'password1')).toBe('')
    expect(acc.account.authMode).toBe('sent')
    expect(acc.account.dialog).toBe('login')
  })

  it('ссылка из письма подтверждает почту, входит и убирает токен из адреса', async () => {
    history.replaceState(null, '', '/?verify=abc123')
    api.verify.mockResolvedValueOnce({ token: 'u2.ok', user })
    const notify = vi.fn()

    expect(await acc.handleEmailLink(notify)).toBe(true)
    expect(api.verify).toHaveBeenCalledWith('abc123')
    expect(localStorage.getItem('ml.user.token')).toBe('u2.ok')
    expect(notify).toHaveBeenCalledWith(expect.stringMatching(/Почта подтверждена/))
    expect(location.search).toBe('')
  })

  it('ссылка сброса открывает окно нового пароля', async () => {
    history.replaceState(null, '', '/?reset=tok')
    expect(await acc.handleEmailLink(vi.fn())).toBe(true)
    expect(acc.account.dialog).toBe('login')
    expect(acc.account.authMode).toBe('reset')

    api.resetPassword.mockResolvedValueOnce({ token: 'u2.reset', user })
    expect(await acc.setNewPassword('новый-пароль')).toBe('')
    expect(api.resetPassword).toHaveBeenCalledWith('tok', 'новый-пароль')
    expect(acc.account.dialog).toBe('')
    expect(localStorage.getItem('ml.user.token')).toBe('u2.reset')
  })
})
