<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { drawOverlay } from '../../lib/heat'
import type { Showcase } from '../../lib/types'

const props = defineProps<{ card: Showcase['card'] }>()

const root = ref<HTMLDivElement>()
const canvas = ref<HTMLCanvasElement>()
const pos = ref(100) // % ширины, правее которого видна карта внимания
const touched = ref(false)
let ro: ResizeObserver | undefined
let raf = 0
let introTimer = 0

function redraw() {
  const el = root.value,
    c = canvas.value
  if (!el || !c) return
  const r = el.getBoundingClientRect()
  drawOverlay(c, props.card.grid, 'heat', r.width, r.height, 0.85)
}

function setFrom(e: PointerEvent) {
  const r = root.value!.getBoundingClientRect()
  pos.value = Math.min(100, Math.max(0, ((e.clientX - r.left) / r.width) * 100))
}
function down(e: PointerEvent) {
  touched.value = true
  cancelAnimationFrame(raf)
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  setFrom(e)
}
function move(e: PointerEvent) {
  if ((e.currentTarget as HTMLElement).hasPointerCapture(e.pointerId)) setFrom(e)
}
const KEY_STEP = 5
const KEYS: Record<string, (p: number) => number> = {
  ArrowLeft: (p) => p - KEY_STEP,
  ArrowDown: (p) => p - KEY_STEP,
  ArrowRight: (p) => p + KEY_STEP,
  ArrowUp: (p) => p + KEY_STEP,
  Home: () => 0,
  End: () => 100,
}

function key(e: KeyboardEvent) {
  const next = KEYS[e.key]
  if (!next) return // Tab и прочие клавиши не трогаем — фокус просто проходит мимо
  e.preventDefault() // иначе стрелки заодно прокручивают страницу
  touched.value = true
  cancelAnimationFrame(raf)
  pos.value = Math.min(100, Math.max(0, next(pos.value)))
}

// подсказка при появлении: шторка сама съезжает к середине; без анимации — сразу встаёт на место
function intro() {
  const from = 100,
    to = 46,
    dur = 1400
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
    if (!touched.value) pos.value = to
    return
  }
  const t0 = performance.now()
  const step = (t: number) => {
    if (touched.value) return
    const k = Math.min(1, (t - t0) / dur)
    const e = 1 - Math.pow(1 - k, 3)
    pos.value = from + (to - from) * e
    if (k < 1) raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)
}

onMounted(() => {
  ro = new ResizeObserver(redraw)
  if (root.value) ro.observe(root.value)
  introTimer = window.setTimeout(intro, 500)
})
onUnmounted(() => {
  ro?.disconnect()
  clearTimeout(introTimer)
  cancelAnimationFrame(raf)
})
watch(() => props.card, redraw)
</script>

<template>
  <div
    ref="root"
    class="ba"
    :style="{ aspectRatio: `${card.width} / ${card.height}`, '--pos': `${pos}%` }"
    role="slider"
    tabindex="0"
    aria-label="Сравнить обложку и карту внимания"
    :aria-valuenow="Math.round(pos)"
    aria-valuemin="0"
    aria-valuemax="100"
    @pointerdown="down"
    @pointermove="move"
    @keydown="key"
  >
    <img :src="card.url" alt="" draggable="false" />
    <div class="heat-side">
      <canvas ref="canvas" />
      <span
        v-for="(f, i) in card.fixations.slice(0, 3)"
        :key="i"
        class="fix num"
        :class="{ first: i === 0 }"
        :style="{ left: `${f.x * 100}%`, top: `${f.y * 100}%` }"
        >{{ i + 1 }}</span
      >
    </div>
    <span class="tag left num">Обложка</span>
    <span class="tag right num">Куда посмотрят</span>
    <div class="divider">
      <span class="handle"><i /><i /></span>
    </div>
  </div>
</template>

<style scoped>
.ba {
  position: relative;
  width: 100%;
  overflow: hidden;
  border-radius: 18px;
  background: var(--sunken);
  cursor: ew-resize;
  user-select: none;
  touch-action: pan-y;
  box-shadow:
    0 40px 80px -40px rgba(0, 0, 0, 0.55),
    0 0 0 1px color-mix(in srgb, var(--ink) 10%, transparent);
}

img,
canvas,
.heat-side {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

img {
  object-fit: fill;
}

.heat-side {
  clip-path: inset(0 0 0 var(--pos));
}

.fix {
  position: absolute;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.95);
  color: var(--on-tile);
  font-size: 13px;
  font-weight: 700;
  box-shadow:
    0 0 0 1.5px var(--on-tile),
    0 6px 16px rgba(0, 0, 0, 0.35);
}

.fix.first {
  background: var(--accent);
  color: var(--on-accent);
}

.tag {
  position: absolute;
  top: 14px;
  padding: 4px 9px;
  border-radius: 6px;
  background: rgba(14, 14, 12, 0.72);
  color: #fff;
  font-size: 11px;
  letter-spacing: 0.02em;
  backdrop-filter: blur(6px);
  pointer-events: none;
}

.tag.left {
  left: 14px;
}

.tag.right {
  right: 14px;
}

.divider {
  position: absolute;
  top: 0;
  bottom: 0;
  left: var(--pos);
  width: 2px;
  margin-left: -1px;
  background: #fff;
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.15),
    0 0 20px rgba(0, 0, 0, 0.35);
  pointer-events: none;
}

.handle {
  position: absolute;
  top: 50%;
  left: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 42px;
  height: 42px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.handle i {
  width: 2px;
  height: 14px;
  border-radius: 1px;
  background: var(--on-tile);
}
</style>
