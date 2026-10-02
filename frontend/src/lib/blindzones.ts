import { aoiStat } from './heat'
import type { Grid } from './types'

/**
 * Слепые зоны карточки Wildberries — углы, которые в выдаче закрывает интерфейс площадки:
 * бейджи NEW/ХИТ, «избранное», скидка с промо-плашками и кнопка корзины.
 * Координаты — доли карточки 3:4 (обложка в выдаче обрезается «по центру», как object-fit: cover).
 * Размеры сняты со скриншотов мобильного приложения WB с запасом на длинные плашки.
 */
export interface BlindZone {
  id: 'badges' | 'favorite' | 'discount' | 'buy'
  title: string
  /** что здесь рисует WB */
  covers: string
  /** совет, если зона занята */
  advice: string
  x: number
  y: number
  w: number
  h: number
}

export const BLIND_ZONES: BlindZone[] = [
  {
    id: 'badges',
    title: 'Бейджи',
    covers: 'NEW, ХИТ, «Оригинал»',
    advice: 'Логотип или плашку из этого угла перекроют бейджи — сдвиньте их ниже или к центру.',
    x: 0,
    y: 0,
    w: 0.3,
    h: 0.15,
  },
  {
    id: 'favorite',
    title: 'Избранное',
    covers: 'сердечко «в избранное»',
    advice: 'Сюда WB ставит сердечко — стикер или надпись в этом углу будет частично закрыта.',
    x: 0.8,
    y: 0,
    w: 0.2,
    h: 0.14,
  },
  {
    id: 'discount',
    title: 'Скидка и промо',
    covers: '−47%, «Клиентские дни», «Промотовар»',
    advice:
      'Скидка и до трёх промо-плашек занимают левый нижний угол — не ставьте сюда объём, цену или главный бенефит.',
    x: 0,
    y: 0.78,
    w: 0.52,
    h: 0.22,
  },
  {
    id: 'buy',
    title: 'Корзина',
    covers: 'кнопка корзины',
    advice: 'На части экранов здесь круглая кнопка корзины — важное отсюда лучше убрать.',
    x: 0.8,
    y: 0.84,
    w: 0.2,
    h: 0.16,
  },
]

export type ZoneLevel = 'free' | 'light' | 'busy'

export interface ZoneCheck {
  zone: BlindZone
  level: ZoneLevel
  /** доля пикселей с резкими краями: текст, плашки, контуры товара */
  edges: number
  /** доля внимания покупателя, которая приходится на зону (по карте внимания) */
  attention: number
}

// Пороги откалиброваны на обложках примеров: пустой угол даёт <2% краёв, надпись или плашка — от 4,5%.
const EDGE_BUSY = 0.045
const EDGE_LIGHT = 0.02
const SPOT_LIGHT = 0.35 // доля пикселей, заметно отличных по цвету от фона угла
const EDGE_STEP = 40 // перепад яркости соседних пикселей, который считаем краем
const SPOT_DIST = 45 // расстояние в RGB от медианного цвета угла
const CARD_W = 300
const CARD_H = 400

/** Как обложка ложится в карточку 3:4: какая часть картинки видна (доли от её сторон). */
export function coverCrop(width: number, height: number) {
  const target = 3 / 4
  const ratio = width / height
  if (ratio > target) {
    const w = target / ratio
    return { x: (1 - w) / 2, y: 0, w, h: 1 }
  }
  const h = ratio / target
  return { x: 0, y: (1 - h) / 2, w: 1, h }
}

/** Зона карточки → прямоугольник в долях исходной картинки (для карты внимания). */
export function zoneInImage(zone: BlindZone, width: number, height: number) {
  const c = coverCrop(width, height)
  return { x: c.x + zone.x * c.w, y: c.y + zone.y * c.h, w: zone.w * c.w, h: zone.h * c.h }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

function measure(px: Uint8ClampedArray, zone: BlindZone) {
  const x0 = Math.round(zone.x * CARD_W)
  const y0 = Math.round(zone.y * CARD_H)
  const x1 = Math.round((zone.x + zone.w) * CARD_W)
  const y1 = Math.round((zone.y + zone.h) * CARD_H)
  const lum = (x: number, y: number) => {
    const i = (y * CARD_W + x) * 4
    return 0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2]
  }
  let edges = 0
  let total = 0
  const rs: number[] = []
  const gs: number[] = []
  const bs: number[] = []
  for (let y = y0; y < y1 - 1; y++)
    for (let x = x0; x < x1 - 1; x++) {
      const l = lum(x, y)
      if (Math.abs(lum(x + 1, y) - l) + Math.abs(lum(x, y + 1) - l) > EDGE_STEP) edges++
      const i = (y * CARD_W + x) * 4
      rs.push(px[i])
      gs.push(px[i + 1])
      bs.push(px[i + 2])
      total++
    }
  const med = (a: number[]) => a.sort((p, q) => p - q)[Math.floor(a.length / 2)] ?? 0
  const [mr, mg, mb] = [med([...rs]), med([...gs]), med([...bs])]
  let spots = 0
  for (let k = 0; k < rs.length; k++) if (Math.hypot(rs[k] - mr, gs[k] - mg, bs[k] - mb) > SPOT_DIST) spots++
  return { edges: total ? edges / total : 0, spots: total ? spots / total : 0 }
}

const cache = new Map<string, Promise<ZoneCheck[]>>()

/** Проверяет слепые зоны обложки. Результат кэшируется по адресу картинки. */
export function checkBlindZones(src: string, width: number, height: number, grid?: Grid): Promise<ZoneCheck[]> {
  const key = src
  let job = cache.get(key)
  if (!job) {
    job = loadImage(src).then((img) => {
      const canvas = document.createElement('canvas')
      canvas.width = CARD_W
      canvas.height = CARD_H
      const ctx = canvas.getContext('2d', { willReadFrequently: true })
      if (!ctx) return []
      const c = coverCrop(img.naturalWidth || width, img.naturalHeight || height)
      const nw = img.naturalWidth || width
      const nh = img.naturalHeight || height
      ctx.drawImage(img, c.x * nw, c.y * nh, c.w * nw, c.h * nh, 0, 0, CARD_W, CARD_H)
      const px = ctx.getImageData(0, 0, CARD_W, CARD_H).data
      return BLIND_ZONES.map((zone) => {
        const m = measure(px, zone)
        const level: ZoneLevel =
          m.edges >= EDGE_BUSY ? 'busy' : m.edges >= EDGE_LIGHT || m.spots >= SPOT_LIGHT ? 'light' : 'free'
        const attention = grid ? aoiStat(grid, zoneInImage(zone, width, height)).share : 0
        return { zone, level, edges: m.edges, attention }
      })
    })
    cache.set(key, job)
    job.catch(() => cache.delete(key))
  }
  return job
}
