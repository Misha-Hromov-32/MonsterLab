import { describe, expect, it } from 'vitest'
import { isImage } from './files'

const file = (name: string, type = '') => new File(['x'], name, { type })

describe('isImage', () => {
  it('принимает JPG, PNG и WebP по MIME-типу', () => {
    expect(isImage(file('a', 'image/jpeg'))).toBe(true)
    expect(isImage(file('a', 'image/png'))).toBe(true)
    expect(isImage(file('a', 'image/webp'))).toBe(true)
  })

  it('без MIME-типа смотрит на расширение, регистр не важен', () => {
    expect(isImage(file('photo.jpg'))).toBe(true)
    expect(isImage(file('photo.JPEG'))).toBe(true)
    expect(isImage(file('photo.Png'))).toBe(true)
    expect(isImage(file('photo.webp'))).toBe(true)
  })

  it('отклоняет HEIC, AVIF, GIF и PDF', () => {
    expect(isImage(file('a.heic', 'image/heic'))).toBe(false)
    expect(isImage(file('a.heic'))).toBe(false)
    expect(isImage(file('a.avif', 'image/avif'))).toBe(false)
    expect(isImage(file('a.gif', 'image/gif'))).toBe(false)
    expect(isImage(file('a.pdf', 'application/pdf'))).toBe(false)
  })
})
