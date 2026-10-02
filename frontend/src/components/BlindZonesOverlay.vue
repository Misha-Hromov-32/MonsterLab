<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Check, Heart, ShoppingCart, TriangleAlert } from 'lucide-vue-next'
import { BLIND_ZONES, coverCrop, zoneInImage, type ZoneCheck } from '../lib/blindzones'

// Слой поверх обложки: «Зоны» — где Wildberries рисует свои элементы и что в этих углах сейчас;
// «Как в WB» — те же углы, заполненные настоящими бейджами, сердечком, плашками и корзиной.
const props = defineProps<{ width: number; height: number; checks: ZoneCheck[] | null; view: 'zones' | 'wb' }>()

const root = ref<HTMLDivElement>()
const boxW = ref(0)
let ro: ResizeObserver | undefined
onMounted(() => {
  ro = new ResizeObserver(([e]) => (boxW.value = e.contentRect.width))
  if (root.value) ro.observe(root.value)
})
onUnmounted(() => ro?.disconnect())

const crop = computed(() => coverCrop(props.width, props.height))
// всё в процентах от картинки, размеры шрифтов — от ширины карточки 3:4
const cardPx = computed(() => boxW.value * crop.value.w)
const pct = (r: { x: number; y: number; w: number; h: number }) => ({
  left: `${r.x * 100}%`,
  top: `${r.y * 100}%`,
  width: `${r.w * 100}%`,
  height: `${r.h * 100}%`,
})
/** точка карточки (доли 3:4) → позиция в процентах картинки */
const at = (x: number, y: number) => ({
  left: `${(crop.value.x + x * crop.value.w) * 100}%`,
  top: `${(crop.value.y + y * crop.value.h) * 100}%`,
})

const zones = computed(() =>
  BLIND_ZONES.map((zone) => ({
    zone,
    check: props.checks?.find((c) => c.zone.id === zone.id),
    style: pct(zoneInImage(zone, props.width, props.height)),
  })),
)
// часть картинки, которую WB обрежет (обложка не 3:4)
const outside = computed(() => crop.value.w < 0.999 || crop.value.h < 0.999)
</script>

<template>
  <div ref="root" class="bz" :class="view" :style="{ '--u': `${cardPx / 100}px` }" aria-hidden="true">
    <template v-if="outside">
      <div class="cut" :style="pct({ x: 0, y: 0, w: crop.x || 1, h: crop.y || 1 })" />
      <div
        class="cut"
        :style="
          pct({ x: crop.x + crop.w, y: crop.y + crop.h, w: 1 - crop.x - crop.w || 1, h: 1 - crop.y - crop.h || 1 })
        "
      />
    </template>

    <template v-if="view === 'zones'">
      <div
        v-for="z in zones"
        :key="z.zone.id"
        class="zone"
        :class="[z.zone.id, z.check?.level ?? 'free']"
        :style="z.style"
      >
        <span class="tag">
          <TriangleAlert v-if="z.check?.level === 'busy'" class="ic" />
          <Check v-else-if="z.check?.level === 'free'" class="ic" />
          {{ z.zone.title }}
        </span>
      </div>
    </template>

    <template v-else>
      <span class="wb new" :style="at(0.03, 0.025)">NEW</span>
      <span class="wb heart" :style="at(0.86, 0.022)"><Heart class="hi" /></span>
      <div class="wb promos" :style="at(0.03, 0.8)">
        <span class="p sale">−47%</span>
        <span class="p days">КЛИЕНТСКИЕ ДНИ</span>
        <span class="p promo">ПРОМОТОВАР</span>
      </div>
      <span class="wb cart" :style="at(0.845, 0.86)"><ShoppingCart class="ci" /></span>
    </template>
  </div>
</template>

<style scoped>
.bz {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  /* --u — сотая доля ширины карточки: все размеры элементов WB от неё */
}

.cut {
  position: absolute;
  background: repeating-linear-gradient(-45deg, rgba(28, 28, 28, 0.55) 0 6px, rgba(28, 28, 28, 0.35) 6px 12px);
}

/* ------------------------------------------------ зоны */

.zone {
  position: absolute;
  display: flex;
  padding: 6px;
  border: 1.5px dashed rgba(28, 28, 28, 0.35);
  background: color-mix(in srgb, var(--z) 42%, transparent);
  backdrop-filter: saturate(0.9);
  transition: background 0.2s;
}

.zone.badges {
  --z: #fff3a6;
  border-radius: 0 0 14px 0;
  align-items: flex-end;
}
.zone.favorite {
  --z: #ffc2cc;
  border-radius: 0 0 0 14px;
  justify-content: flex-end;
  align-items: flex-end;
}
.zone.discount {
  --z: #c9f2c4;
  border-radius: 0 14px 0 0;
}
.zone.buy {
  --z: #ffd9b0;
  border-radius: 14px 0 0 0;
  justify-content: flex-end;
}

.zone.busy {
  border: 2px solid #e5484d;
  background: color-mix(in srgb, var(--z) 62%, transparent);
}

.tag {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  flex: none;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.94);
  color: #1c1c1c;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.zone.badges .tag,
.zone.favorite .tag {
  align-self: flex-end;
}

.zone.busy .tag {
  background: #e5484d;
  color: #fff;
}

.ic {
  width: 12px;
  height: 12px;
  flex: none;
}

.zone.free .ic {
  color: #16a35f;
}

/* ------------------------------------------------ как в выдаче WB */

.wb {
  position: absolute;
  font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
  font-weight: 600;
  line-height: 1;
  letter-spacing: 0.01em;
}

.new {
  padding: calc(var(--u) * 0.9) calc(var(--u) * 1.4);
  border-radius: calc(var(--u) * 0.9);
  background: #1db67b;
  color: #fff;
  font-size: calc(var(--u) * 3.6);
}

.heart {
  display: grid;
  place-items: center;
  width: calc(var(--u) * 10);
  height: calc(var(--u) * 10);
}

.hi {
  width: 100%;
  height: 100%;
  color: #1c1c1c;
  fill: #fff;
  stroke-width: 1.8;
  filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.25));
}

.promos {
  display: grid;
  justify-items: start;
  gap: calc(var(--u) * 0.9);
}

.p {
  padding: calc(var(--u) * 0.8) calc(var(--u) * 1.3);
  border-radius: calc(var(--u) * 0.9);
  font-size: calc(var(--u) * 3.4);
  white-space: nowrap;
}

.sale {
  background: #f5157d;
  color: #fff;
}

.days {
  background: linear-gradient(90deg, #f6261f, #ff8a00);
  color: #fff;
}

.promo {
  background: #f7d41a;
  color: #1c1c1c;
}

.cart {
  display: grid;
  place-items: center;
  width: calc(var(--u) * 12);
  height: calc(var(--u) * 12);
  border-radius: 50%;
  background: #cb11ab;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
}

.ci {
  width: 55%;
  height: 55%;
  color: #fff;
}
</style>
