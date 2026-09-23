import type { Aoi, Grid } from './types'

interface Field {
  w: number
  h: number
  v: Float32Array // 0..1
  sum: number
}

const cache = new WeakMap<Grid, Field>()

function field(grid: Grid): Field {
  let f = cache.get(grid)
  if (f) return f
  const bin = atob(grid.data)
  const v = new Float32Array(bin.length)
  let sum = 0
  for (let i = 0; i < bin.length; i++) {
    v[i] = bin.charCodeAt(i) / 255
    sum += v[i]
  }
  f = { w: grid.w, h: grid.h, v, sum }
  cache.set(grid, f)
  return f
}

/** Значение порога, выше которого лежит `mass` всего внимания. */
function massThreshold(f: Field, mass: number): number {
  const sorted = Float32Array.from(f.v).sort().reverse()
  let acc = 0
  const target = mass * f.sum
  for (let i = 0; i < sorted.length; i++) {
    acc += sorted[i]
    if (acc >= target) return sorted[i]
  }
  return 0
}

export interface AoiStat {
  share: number // доля внимания 0..1
  area: number // доля площади 0..1
  lift: number // share / area
}

export function aoiStat(grid: Grid, r: Pick<Aoi, 'x' | 'y' | 'w' | 'h'>): AoiStat {
  const f = field(grid)
  const x0 = Math.max(0, Math.floor(r.x * f.w))
  const x1 = Math.min(f.w, Math.ceil((r.x + r.w) * f.w))
  const y0 = Math.max(0, Math.floor(r.y * f.h))
  const y1 = Math.min(f.h, Math.ceil((r.y + r.h) * f.h))
  let s = 0
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) s += f.v[y * f.w + x]
  const share = f.sum ? s / f.sum : 0
  const area = Math.max(1e-6, r.w * r.h)
  return { share, area, lift: share / area }
}

// ------------------------------------------------------------ цветовая шкала

const STOPS: [number, [number, number, number]][] = [
  [0.0, [40, 62, 190]],
  [0.3, [24, 160, 170]],
  [0.52, [120, 200, 80]],
  [0.68, [250, 214, 60]],
  [0.84, [255, 122, 26]],
  [1.0, [226, 36, 27]],
]

function colormap(t: number): [number, number, number] {
  t = Math.min(1, Math.max(0, t))
  for (let i = 0; i < STOPS.length - 1; i++) {
    const [t0, c0] = STOPS[i]
    const [t1, c1] = STOPS[i + 1]
    if (t <= t1) {
      const k = (t - t0) / (t1 - t0)
      return [c0[0] + (c1[0] - c0[0]) * k, c0[1] + (c1[1] - c0[1]) * k, c0[2] + (c1[2] - c0[2]) * k]
    }
  }
  return STOPS[STOPS.length - 1][1]
}

export const GRADIENT_CSS = `linear-gradient(90deg, ${STOPS.map(([t, c]) => `rgb(${c.join(' ')}) ${t * 100}%`).join(', ')})`

const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)))
  return t * t * (3 - 2 * t)
}

// ------------------------------------------------------------ отрисовка

// Рамка из повторённых крайних пикселей: размытие не «съедает» кромку и карта не сдвигается.
const BORDER = 4

/**
 * Маленький цветной холст карты (сетка + рамка) без учёта плотности: плотность накладывается
 * через globalAlpha, поэтому движение ползунка не пересчитывает цвета по пикселям.
 */
const tiles = new WeakMap<Grid, Map<string, HTMLCanvasElement>>()

function tile(grid: Grid, mode: 'heat' | 'fog', fogColor: string): HTMLCanvasElement {
  let byKey = tiles.get(grid)
  if (!byKey) {
    byKey = new Map()
    tiles.set(grid, byKey)
  }
  const key = mode === 'heat' ? 'heat' : `fog:${fogColor}`
  const cached = byKey.get(key)
  if (cached) return cached

  const f = field(grid)
  const sw = f.w + BORDER * 2
  const sh = f.h + BORDER * 2
  const small = document.createElement('canvas')
  small.width = sw
  small.height = sh
  const sctx = small.getContext('2d')
  if (!sctx) return small
  const img = sctx.createImageData(sw, sh)
  const [fr, fg, fb] = fogColor.split(',').map(Number)
  for (let i = 0; i < sw * sh; i++) {
    const sx = Math.min(f.w - 1, Math.max(0, (i % sw) - BORDER))
    const sy = Math.min(f.h - 1, Math.max(0, Math.floor(i / sw) - BORDER))
    const t = f.v[sy * f.w + sx]
    const o = i * 4
    if (mode === 'heat') {
      const [r, g, b] = colormap(t)
      img.data[o] = r
      img.data[o + 1] = g
      img.data[o + 2] = b
      // холодные зоны почти прозрачны, чтобы не «замыливать» фото вуалью
      img.data[o + 3] = 255 * 0.92 * smooth(0.06, 0.5, t)
    } else {
      img.data[o] = fr
      img.data[o + 1] = fg
      img.data[o + 2] = fb
      img.data[o + 3] = 255 * (1 - smooth(0.08, 0.7, t))
    }
  }
  sctx.putImageData(img, 0, 0)
  byKey.set(key, small)
  return small
}

/** Фон текущей темы (--bg) как «r,g,b» — туман растворяет карточку в странице. */
export function bgRgb(): string {
  const c = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()
  const m = c.match(/^#([0-9a-f]{6})$/i)
  if (!m) return '255,255,255'
  const n = parseInt(m[1], 16)
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`
}

export function drawOverlay(
  canvas: HTMLCanvasElement,
  grid: Grid,
  mode: 'heat' | 'fog',
  cssW: number,
  cssH: number,
  opacity: number,
  fogColor = bgRgb(),
) {
  const dpr = Math.min(2, window.devicePixelRatio || 1)
  const W = Math.max(1, Math.round(cssW * dpr))
  const H = Math.max(1, Math.round(cssH * dpr))
  if (canvas.width !== W) canvas.width = W
  if (canvas.height !== H) canvas.height = H
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, W, H)

  const f = field(grid)
  const small = tile(grid, mode, fogColor)
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  // туман даже на минимальной плотности оставляет лёгкую вуаль, иначе режим не отличить от оригинала
  ctx.globalAlpha = mode === 'heat' ? opacity : 0.25 + 0.72 * opacity
  const kx = W / f.w
  const ky = H / f.h
  ctx.filter = `blur(${Math.max(1.5, kx * 0.9).toFixed(1)}px)`
  ctx.drawImage(small, -BORDER * kx, -BORDER * ky, W + 2 * BORDER * kx, H + 2 * BORDER * ky)
  ctx.filter = 'none'
  ctx.globalAlpha = 1
}

// ------------------------------------------------------------ экспорт

/** Собирает PNG: обложка с картой внимания + подпись с ключевыми цифрами. */
export async function exportPng(opts: {
  src: string
  grid: Grid
  mode: 'heat' | 'fog'
  opacity: number
  title: string
  lines: string[]
  filename: string
}) {
  const img = new Image()
  img.src = opts.src
  await img.decode()
  // не уже 1000 px, иначе подпись с цифрами не помещается
  const W = Math.max(1000, Math.min(1400, img.naturalWidth))
  const H = Math.round((img.naturalHeight * W) / img.naturalWidth)
  const footer = 132
  const c = document.createElement('canvas')
  c.width = W
  c.height = H + footer
  const ctx = c.getContext('2d')
  if (!ctx) return
  ctx.drawImage(img, 0, 0, W, H)
  const overlay = document.createElement('canvas')
  // drawOverlay учитывает devicePixelRatio — компенсируем, чтобы получить ровно W×H
  const dpr = Math.min(2, window.devicePixelRatio || 1)
  // PNG всегда в своей светлой палитре, независимо от темы: туман и подписи — светлые тона из base.css
  drawOverlay(overlay, opts.grid, opts.mode, W / dpr, H / dpr, opts.opacity, '245,244,240')
  ctx.drawImage(overlay, 0, 0, W, H)
  ctx.fillStyle = '#1c1c1c'
  ctx.fillRect(0, H, W, footer)
  ctx.fillStyle = '#dbf570'
  ctx.fillRect(0, H, 6, footer)
  ctx.fillStyle = '#f5f4f0'
  ctx.font = '300 32px "Onest Variable", sans-serif'
  ctx.fillText(opts.title, 32, H + 50)
  ctx.font = '17px "Onest Variable", sans-serif'
  ctx.fillStyle = '#9e9b94'
  opts.lines.forEach((l, i) => ctx.fillText(l, 32, H + 84 + i * 26))
  const a = document.createElement('a')
  a.href = c.toDataURL('image/png')
  a.download = opts.filename
  a.click()
}

// ------------------------------------------------------------ изолинии (marching squares)

function blurField(f: Field, radius = 1): Float32Array {
  const { w, h, v } = f
  const tmp = new Float32Array(v.length)
  const out = new Float32Array(v.length)
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let s = 0
      let c = 0
      for (let d = -radius; d <= radius; d++) {
        const xx = x + d
        if (xx < 0 || xx >= w) continue
        s += v[y * w + xx]
        c++
      }
      tmp[y * w + x] = s / c
    }
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let s = 0
      let c = 0
      for (let d = -radius; d <= radius; d++) {
        const yy = y + d
        if (yy < 0 || yy >= h) continue
        s += tmp[yy * w + x]
        c++
      }
      out[y * w + x] = s / c
    }
  return out
}

/** Изолинии, внутри которых лежит заданная доля внимания. Координаты — в долях 0..1. */
export function contourPaths(grid: Grid, masses: number[]): { mass: number; d: string; anchor: [number, number] }[] {
  const base = field(grid)
  const v = blurField(base, 1)
  const f: Field = { w: base.w, h: base.h, v, sum: v.reduce((a, b) => a + b, 0) }
  const { w, h } = f
  const at = (x: number, y: number) => (x < 0 || y < 0 || x >= w || y >= h ? 0 : v[y * w + x])
  return masses.map((mass) => {
    const thr = massThreshold(f, mass)
    const segs: string[] = []
    // подпись ставим у самой правой точки контура: у вложенных линий они не совпадают
    let anchor: [number, number] = [-1, 0]
    const lerp = (a: number, b: number) => (thr - a) / (b - a || 1e-9)
    // сетка расширена на 1 ячейку, чтобы контуры замыкались у краёв
    for (let y = -1; y < h; y++)
      for (let x = -1; x < w; x++) {
        const a = at(x, y)
        const b = at(x + 1, y)
        const c = at(x + 1, y + 1)
        const d = at(x, y + 1)
        const idx = (a >= thr ? 8 : 0) | (b >= thr ? 4 : 0) | (c >= thr ? 2 : 0) | (d >= thr ? 1 : 0)
        if (idx === 0 || idx === 15) continue
        const top: [number, number] = [x + lerp(a, b), y]
        const right: [number, number] = [x + 1, y + lerp(b, c)]
        const bottom: [number, number] = [x + lerp(d, c), y + 1]
        const left: [number, number] = [x, y + lerp(a, d)]
        const lines: [number, number][][] = []
        switch (idx) {
          case 1:
          case 14:
            lines.push([left, bottom])
            break
          case 2:
          case 13:
            lines.push([bottom, right])
            break
          case 3:
          case 12:
            lines.push([left, right])
            break
          case 4:
          case 11:
            lines.push([top, right])
            break
          case 5:
            lines.push([left, top], [bottom, right])
            break
          case 6:
          case 9:
            lines.push([top, bottom])
            break
          case 7:
          case 8:
            lines.push([left, top])
            break
          case 10:
            lines.push([top, right], [left, bottom])
            break
        }
        for (const [p, q] of lines) {
          const px = (p[0] + 0.5) / w
          const py = (p[1] + 0.5) / h
          const qx = (q[0] + 0.5) / w
          const qy = (q[1] + 0.5) / h
          segs.push(`M${px.toFixed(4)} ${py.toFixed(4)}L${qx.toFixed(4)} ${qy.toFixed(4)}`)
          if (px > anchor[0]) anchor = [px, py]
          if (qx > anchor[0]) anchor = [qx, qy]
        }
      }
    return { mass, d: segs.join(''), anchor }
  })
}
