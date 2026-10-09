import { describe, expect, it } from 'vitest'
import { srcset } from './images'

describe('уменьшенные картинки примеров', () => {
  it('для картинки примера — набор WebP-ширин', () => {
    expect(srcset('/api/public/files/e7071e4501/14c5a99af2.jpg')).toBe(
      '/api/public/files/e7071e4501/14c5a99af2.jpg?w=160 160w, /api/public/files/e7071e4501/14c5a99af2.jpg?w=320 320w, ' +
        '/api/public/files/e7071e4501/14c5a99af2.jpg?w=480 480w, /api/public/files/e7071e4501/14c5a99af2.jpg?w=800 800w',
    )
  })

  it('чужие адреса не трогаем', () => {
    expect(srcset('blob:https://monstorelab.ru/123')).toBeUndefined()
    expect(srcset('/api/library/abc/preview')).toBeUndefined()
  })
})
