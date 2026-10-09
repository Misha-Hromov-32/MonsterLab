import { consent } from './consent'

/**
 * Яндекс Метрика — только с согласия на аналитические cookie (плашка). Номер счётчика приходит с сервера
 * (METRIKA_ID в .env), без него и без согласия скрипт не загружается, а goal()/hit() ничего не делают.
 * Вебвизор не записывает содержимое полей (так настроено в счётчике); тексты с почтой помечены ym-hide-content.
 *
 * Цели (идентификаторы — как в настройках счётчика): upload_click, register, email_verified, oauth_login,
 * analysis, tariffs_open, checkout, payment (с суммой order_price), promo.
 */
type Ym = (id: number, method: string, ...args: unknown[]) => void
declare global {
  interface Window {
    ym?: Ym & { a?: unknown[]; l?: number }
  }
}

let counter = 0

export function initMetrika(id: number | null | undefined) {
  if (!id || counter || consent.choice !== 'all') return
  counter = id
  // официальный загрузчик Метрики: очередь вызовов до загрузки tag.js
  const w = window
  w.ym =
    w.ym ||
    (Object.assign(
      function (...args: unknown[]) {
        ;(w.ym!.a = w.ym!.a || []).push(args)
      },
      { l: Date.now() },
    ) as Window['ym'])
  const s = document.createElement('script')
  s.async = true
  s.src = `https://mc.yandex.ru/metrika/tag.js?id=${id}`
  document.head.appendChild(s)
  w.ym!(id, 'init', {
    webvisor: true,
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    referrer: document.referrer,
    url: location.href,
  })
}

/** Достижение цели. params — например { order_price: 990, currency: 'RUB' } для оплаты. */
export function goal(name: string, params?: Record<string, unknown>) {
  if (!counter || !window.ym) return
  window.ym(counter, 'reachGoal', name, params)
}

/** Просмотр «страницы» внутри одностраничного приложения (разбор, сравнение, полка). */
export function hit(url: string, title = document.title) {
  if (!counter || !window.ym) return
  window.ym(counter, 'hit', url, { title, referer: location.href })
}
