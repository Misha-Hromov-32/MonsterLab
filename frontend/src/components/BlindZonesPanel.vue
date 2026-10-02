<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { state } from '../store'
import { checkBlindZones, type ZoneCheck, type ZoneLevel } from '../lib/blindzones'
import type { Analysis, Variant } from '../lib/types'

// Сводка по слепым зонам WB в инспекторе: что в каждом углу и сколько внимания туда уходит.
const props = defineProps<{ variant: Variant; analysis: Analysis }>()

const checks = ref<ZoneCheck[] | null>(null)
const failed = ref(false)
watch(
  () => props.variant.url,
  async (url) => {
    checks.value = null
    failed.value = false
    try {
      const res = await checkBlindZones(url, props.analysis.width, props.analysis.height, props.analysis.grid)
      if (props.variant.url === url) checks.value = res
    } catch {
      failed.value = true
    }
  },
  { immediate: true },
)

const LEVEL: Record<ZoneLevel, string> = { free: 'свободно', light: 'есть детали', busy: 'занято' }
const busy = computed(() => checks.value?.filter((c) => c.level === 'busy') ?? [])
const summary = computed(() => {
  if (!checks.value) return ''
  if (!busy.value.length) return 'Все четыре угла свободны — бейджи WB ничего важного не закроют.'
  const n = busy.value.length
  return `${n === 1 ? 'Один угол занят' : `Заняты ${n} угла`} — элементы WB лягут поверх вашего дизайна.`
})
</script>

<template>
  <section>
    <div class="sec-head">
      <span class="label">Слепые зоны WB</span>
      <button class="link" @click="state.blind = state.blind ? '' : 'zones'">
        {{ state.blind ? 'скрыть' : 'показать на обложке' }}
      </button>
    </div>
    <p v-if="failed" class="hint">Не удалось прочитать картинку для проверки углов.</p>
    <p v-else-if="!checks" class="hint">Проверяем углы…</p>
    <template v-else>
      <p class="hint">{{ summary }}</p>
      <ul class="zones">
        <li v-for="c in checks" :key="c.zone.id" :class="c.level">
          <i class="sw" :class="c.zone.id" />
          <div>
            <div class="row">
              <strong>{{ c.zone.title }}</strong>
              <span class="lvl">{{ LEVEL[c.level] }}</span>
              <span class="att num" title="Доля внимания покупателя в этом углу"
                >{{ Math.round(c.attention * 100) }}%</span
              >
            </div>
            <p>{{ c.level === 'busy' ? c.zone.advice : `Здесь WB рисует ${c.zone.covers}.` }}</p>
          </div>
        </li>
      </ul>
      <p class="foot num">% — доля внимания, которая приходится на угол</p>
    </template>
  </section>
</template>

<style scoped>
.sec-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

.link {
  padding: 0;
  border: 0;
  background: none;
  font-size: 12px;
  color: var(--ink-2);
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}

.link:hover {
  color: var(--ink);
}

.hint {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}

.zones {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.zones li {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
}

.sw {
  width: 12px;
  height: 12px;
  margin-top: 3px;
  border-radius: 3px;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12);
}
.sw.badges {
  background: #fff3a6;
}
.sw.favorite {
  background: #ffc2cc;
}
.sw.discount {
  background: #c9f2c4;
}
.sw.buy {
  background: #ffd9b0;
}

.row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.row strong {
  font-size: 13.5px;
  font-weight: 600;
}

.lvl {
  font-size: 12px;
  color: var(--good);
}

.light .lvl {
  color: var(--warn);
}

.busy .lvl {
  color: var(--bad);
}

.att {
  margin-left: auto;
  font-size: 12px;
  color: var(--ink-3);
}

.zones p {
  margin: 2px 0 0;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--ink-2);
}

.foot {
  margin: 10px 0 0;
  font-size: 10.5px;
  color: var(--ink-3);
}
</style>
