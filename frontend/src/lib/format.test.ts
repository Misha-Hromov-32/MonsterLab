import { describe, expect, it } from 'vitest'
import { SCORE_GOOD, SCORE_WARN } from './constants'
import { modelName, pct, plural, silentExperts, tone } from './format'

describe('pct', () => {
  it('переводит долю в проценты', () => {
    expect(pct(0.5)).toBe('50%')
    expect(pct(0.1234, 1)).toBe('12.3%')
    expect(pct(1)).toBe('100%')
  })
})

describe('tone', () => {
  it('границы порогов включительно', () => {
    expect(tone(SCORE_GOOD)).toBe('good')
    expect(tone(SCORE_GOOD - 0.1)).toBe('warn')
    expect(tone(SCORE_WARN)).toBe('warn')
    expect(tone(SCORE_WARN - 0.1)).toBe('bad')
    expect(tone(100)).toBe('good')
    expect(tone(0)).toBe('bad')
  })
})

describe('plural', () => {
  const forms: [string, string, string] = ['вариант', 'варианта', 'вариантов']
  it.each([
    [1, 'вариант'],
    [2, 'варианта'],
    [5, 'вариантов'],
    [11, 'вариантов'],
    [12, 'вариантов'],
    [21, 'вариант'],
    [22, 'варианта'],
    [25, 'вариантов'],
    [111, 'вариантов'],
  ])('%i → %s', (n, word) => {
    expect(plural(n, forms)).toBe(word)
  })
})

describe('silentExperts', () => {
  it('согласует число с обоими словами', () => {
    expect(silentExperts(1)).toBe('1 эксперт не ответил')
    expect(silentExperts(2)).toBe('2 эксперта не ответили')
    expect(silentExperts(5)).toBe('5 экспертов не ответили')
    expect(silentExperts(21)).toBe('21 эксперт не ответил')
  })
})

describe('modelName', () => {
  it.each([
    ['google/gemini-2.5-flash', 'Gemini 2.5 Flash'],
    ['anthropic/claude-haiku-4-5', 'Claude Haiku 4.5'],
    ['openai/gpt-5.4', 'GPT-5.4'],
  ])('%s → %s', (id, name) => {
    expect(modelName(id)).toBe(name)
  })
})
