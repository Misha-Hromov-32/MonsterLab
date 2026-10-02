import { describe, expect, it } from 'vitest'
import { BLIND_ZONES, coverCrop, zoneInImage } from './blindzones'

const zone = (id: string) => BLIND_ZONES.find((z) => z.id === id)!

describe('coverCrop', () => {
  it('обложка 3:4 видна целиком', () => {
    expect(coverCrop(900, 1200)).toEqual({ x: 0, y: 0, w: 1, h: 1 })
  })

  it('квадрат обрезается по бокам, по центру', () => {
    const c = coverCrop(1000, 1000)
    expect(c.w).toBeCloseTo(0.75)
    expect(c.x).toBeCloseTo(0.125)
    expect(c.h).toBe(1)
  })

  it('высокая картинка обрезается сверху и снизу', () => {
    const c = coverCrop(900, 1600)
    expect(c.w).toBe(1)
    expect(c.h).toBeCloseTo(0.75)
    expect(c.y).toBeCloseTo((1 - c.h) / 2)
  })
})

describe('zoneInImage', () => {
  it('на обложке 3:4 совпадает с зоной карточки', () => {
    const r = zoneInImage(zone('discount'), 900, 1200)
    expect(r).toEqual({ x: 0, y: 0.78, w: 0.52, h: 0.22 })
  })

  it('на квадрате сдвигается внутрь видимой части', () => {
    const r = zoneInImage(zone('favorite'), 1000, 1000)
    expect(r.x).toBeCloseTo(0.125 + 0.8 * 0.75)
    expect(r.x + r.w).toBeCloseTo(0.875)
  })
})

describe('BLIND_ZONES', () => {
  it('все зоны лежат внутри карточки и не пересекаются', () => {
    for (const z of BLIND_ZONES) {
      expect(z.x + z.w).toBeLessThanOrEqual(1)
      expect(z.y + z.h).toBeLessThanOrEqual(1)
    }
    for (const a of BLIND_ZONES)
      for (const b of BLIND_ZONES) {
        if (a === b) continue
        const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
        expect(overlap, `${a.id} × ${b.id}`).toBe(false)
      }
  })
})
