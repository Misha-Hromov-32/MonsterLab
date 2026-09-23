<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { aoiStat, bgRgb, contourPaths, drawOverlay } from '../lib/heat'
import { hasOpacity } from '../lib/overlay'
import type { Aoi, Fixation, Grid, OverlayMode } from '../lib/types'

const props = withDefaults(
  defineProps<{
    src: string
    width: number
    height: number
    grid?: Grid
    fixations?: Fixation[]
    mode: OverlayMode
    opacity?: number
    aois?: Aoi[]
    editable?: boolean
    compact?: boolean
    highlight?: { x: number; y: number; w: number; h: number } | null
  }>(),
  { opacity: 0.8, aois: () => [], fixations: () => [], editable: false, compact: false, highlight: null },
)

const emit = defineEmits<{ create: [rect: { x: number; y: number; w: number; h: number }] }>()

const root = ref<HTMLDivElement>()
const canvas = ref<HTMLCanvasElement>()
const size = ref({ w: 0, h: 0 })
let ro: ResizeObserver | undefined
let themeObs: MutationObserver | undefined

function redraw() {
  const c = canvas.value
  if (!c) return
  const { grid, mode } = props
  if (!grid || !hasOpacity(mode) || !size.value.w) {
    c.getContext('2d')?.clearRect(0, 0, c.width, c.height)
    return
  }
  drawOverlay(c, grid, mode, size.value.w, size.value.h, props.opacity, bgRgb())
}

onMounted(() => {
  ro = new ResizeObserver(([e]) => {
    size.value = { w: e.contentRect.width, h: e.contentRect.height }
  })
  if (root.value) ro.observe(root.value)
  // смена темы меняет цвет тумана
  themeObs = new MutationObserver(redraw)
  themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})
onUnmounted(() => {
  ro?.disconnect()
  themeObs?.disconnect()
})

watch(() => [props.grid, props.mode, props.opacity, size.value], redraw)

const contours = computed(() =>
  props.grid && props.mode === 'contours' ? contourPaths(props.grid, [0.25, 0.5, 0.75]) : [],
)

// подписи изолиний раздвигаем, чтобы не наезжали друг на друга
const labels = computed(() => {
  const placed: { x: number; y: number; text: string; flip: boolean }[] = []
  for (const c of contours.value) {
    if (!c.d) continue
    let [x, y] = c.anchor
    while (placed.some((p) => Math.abs(p.x - x) < 0.08 && Math.abs(p.y - y) < 0.035)) y += 0.035
    // у правого края подпись уходит внутрь кадра
    placed.push({ x, y, text: `${Math.round(c.mass * 100)}%`, flip: x > 0.85 })
  }
  return placed
})

const stats = computed(() => {
  const grid = props.grid
  return grid ? props.aois.map((a) => ({ a, s: aoiStat(grid, a) })) : []
})

// ------------------------------------------------------------ рисование зон
const draft = ref<{ x0: number; y0: number; x1: number; y1: number } | null>(null)

function norm(e: PointerEvent) {
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  return {
    x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
    y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
  }
}
function down(e: PointerEvent) {
  if (!props.editable || e.button !== 0) return
  const p = norm(e)
  draft.value = { x0: p.x, y0: p.y, x1: p.x, y1: p.y }
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}
function move(e: PointerEvent) {
  if (!draft.value) return
  const p = norm(e)
  draft.value.x1 = p.x
  draft.value.y1 = p.y
}
function up() {
  const d = draft.value
  draft.value = null
  if (!d) return
  const rect = { x: Math.min(d.x0, d.x1), y: Math.min(d.y0, d.y1), w: Math.abs(d.x1 - d.x0), h: Math.abs(d.y1 - d.y0) }
  if (rect.w > 0.02 && rect.h > 0.02) emit('create', rect)
}
const draftRect = computed(() => {
  const d = draft.value
  if (!d) return null
  return { x: Math.min(d.x0, d.x1), y: Math.min(d.y0, d.y1), w: Math.abs(d.x1 - d.x0), h: Math.abs(d.y1 - d.y0) }
})

const box = (r: { x: number; y: number; w: number; h: number }) => ({
  left: `${r.x * 100}%`,
  top: `${r.y * 100}%`,
  width: `${r.w * 100}%`,
  height: `${r.h * 100}%`,
})
</script>

<template>
  <div
    ref="root"
    class="heat"
    :class="{ editable, compact }"
    :style="{ aspectRatio: `${width} / ${height}` }"
    @pointerdown="down"
    @pointermove="move"
    @pointerup="up"
    @pointercancel="draft = null"
  >
    <img :src="src" alt="" draggable="false" />
    <canvas ref="canvas" class="layer" />

    <svg v-if="mode === 'contours' && contours.length" class="layer" viewBox="0 0 1 1" preserveAspectRatio="none">
      <path v-for="(c, i) in contours" :key="'s' + i" :d="c.d" class="iso-shadow" vector-effect="non-scaling-stroke" />
      <path
        v-for="(c, i) in contours"
        :key="i"
        :d="c.d"
        class="iso"
        :class="'iso-' + i"
        vector-effect="non-scaling-stroke"
      />
    </svg>
    <template v-if="mode === 'contours' && !compact">
      <span
        v-for="(l, i) in labels"
        :key="'l' + i"
        class="iso-label num"
        :class="{ flip: l.flip }"
        :style="{ left: `${l.x * 100}%`, top: `${l.y * 100}%` }"
      >
        {{ l.text }}
      </span>
    </template>

    <template v-if="mode === 'gaze' && fixations.length">
      <svg class="layer" viewBox="0 0 1 1" preserveAspectRatio="none">
        <polyline
          :points="fixations.map((f) => `${f.x},${f.y}`).join(' ')"
          class="path"
          vector-effect="non-scaling-stroke"
        />
      </svg>
      <span
        v-for="(f, i) in fixations"
        :key="i"
        class="fix num"
        :class="{ first: i === 0 }"
        :style="{
          left: `${f.x * 100}%`,
          top: `${f.y * 100}%`,
          '--r': `${compact ? 18 : 26 + Math.sqrt(f.mass) * 40}px`,
        }"
      >
        {{ i + 1 }}
      </span>
    </template>

    <div v-if="highlight" class="hl" :style="box(highlight)" />

    <div v-for="{ a, s } in stats" :key="a.id" class="aoi" :style="box(a)" @pointerdown.stop>
      <span v-if="!compact" class="aoi-tag num" :class="{ inside: a.y < 0.05 }"
        >{{ a.label }} · {{ Math.round(s.share * 100) }}%</span
      >
    </div>
    <div v-if="draftRect" class="aoi draft" :style="box(draftRect)" />
  </div>
</template>

<style scoped>
.heat {
  position: relative;
  width: 100%;
  overflow: hidden;
  border-radius: 4px;
  background: var(--sunken);
  user-select: none;
}

/* жесты гасим только там, где рисуют зоны, — иначе на телефоне страница не прокручивается пальцем по картинке */
.heat.editable {
  cursor: crosshair;
  touch-action: none;
}

img,
.layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

img {
  object-fit: fill;
}

.layer {
  pointer-events: none;
}

.iso,
.iso-shadow {
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.iso-shadow {
  stroke: rgba(0, 0, 0, 0.45);
  stroke-width: 4;
}

.iso {
  stroke: #fff;
  stroke-width: 1.6;
}

.iso-0 {
  stroke: var(--accent);
  stroke-width: 2.2;
}

.iso-2 {
  stroke-dasharray: 3 4;
  stroke-width: 1.3;
}

.compact .iso-shadow {
  stroke-width: 2.5;
}
.compact .iso {
  stroke-width: 1.1;
}

.iso-label {
  position: absolute;
  transform: translate(6px, -50%);
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(10, 10, 9, 0.78);
  color: #fff;
  font-size: 10px;
  pointer-events: none;
  white-space: nowrap;
}

.iso-label.flip {
  transform: translate(calc(-100% - 6px), -50%);
}

.path {
  fill: none;
  stroke: rgba(255, 255, 255, 0.9);
  stroke-width: 1.5;
  stroke-dasharray: 4 4;
  filter: drop-shadow(0 0 1px rgba(0, 0, 0, 0.8));
}

.fix {
  position: absolute;
  display: grid;
  place-items: center;
  width: var(--r);
  height: var(--r);
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.94);
  color: var(--on-tile);
  font-size: 12px;
  font-weight: 700;
  box-shadow:
    0 0 0 1.5px var(--on-tile),
    0 4px 14px rgba(0, 0, 0, 0.35);
  pointer-events: none;
}

.compact .fix {
  font-size: 10px;
}

.fix.first {
  background: var(--accent);
  color: var(--on-accent);
}

.aoi {
  position: absolute;
  border: 1.5px solid #fff;
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.55),
    inset 0 0 0 1px rgba(0, 0, 0, 0.25);
  border-radius: 3px;
}

.aoi.draft {
  border-style: dashed;
  background: rgba(255, 255, 255, 0.08);
}

.aoi-tag {
  position: absolute;
  left: -1.5px;
  top: -1.5px;
  transform: translateY(-100%);
  padding: 2px 6px;
  border-radius: 3px 3px 0 0;
  background: #fff;
  color: var(--on-tile);
  font-size: 10.5px;
  font-weight: 600;
  white-space: nowrap;
}

.aoi-tag.inside {
  left: 0;
  top: 0;
  transform: none;
  border-radius: 0 0 3px 0;
}

.hl {
  position: absolute;
  outline: 2.5px solid var(--accent);
  outline-offset: 1px;
  border-radius: 2px;
  pointer-events: none;
}
</style>
