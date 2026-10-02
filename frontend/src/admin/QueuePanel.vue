<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { adminApi } from './adminApi'
import type { AdminQueue } from '../lib/types'

// Очередь сейчас: загрузка полос и все задачи, которые ждут или выполняются. Обновляется сама.
const REFRESH_MS = 2000
const data = ref<AdminQueue | null>(null)
const error = ref('')
let timer = 0

async function load() {
  try {
    data.value = await adminApi.queue()
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  }
}

onMounted(() => {
  load()
  timer = window.setInterval(load, REFRESH_MS)
})
onUnmounted(() => clearInterval(timer))

const sec = (s: number) =>
  s < 60 ? `${s.toFixed(s < 10 ? 1 : 0)} с` : `${Math.floor(s / 60)} мин ${Math.round(s % 60)} с`
const PLAN: Record<string, string> = { demo: 'Демо', start: 'Старт', pro: 'Про', agency: 'Агентство' }
</script>

<template>
  <div class="panel wide">
    <header class="ph">
      <div>
        <h1>Очередь</h1>
        <p>
          Тяжёлые задачи идут через очередь: у каждой полосы своё число исполнителей. Сначала старшие тарифы, внутри
          тарифа — кто раньше пришёл; пересчёт примеров — последним. Обновляется каждые 2 секунды.
        </p>
      </div>
    </header>
    <p v-if="error" class="err">{{ error }}</p>
    <div v-if="!data" class="loading"><Loader2 :size="18" class="spin" /> Загружаем…</div>

    <template v-if="data">
      <section class="lanes">
        <div v-for="l in data.lanes" :key="l.id" class="card lane">
          <div class="lh">
            <span class="label">{{ l.title }}</span>
            <span class="num busy" :class="{ hot: l.waiting > 0 }">{{ l.running }} / {{ l.workers }}</span>
          </div>
          <div class="slots">
            <i v-for="n in l.workers" :key="n" :class="{ on: n <= l.running }" />
          </div>
          <dl>
            <div>
              <dt>Ждут</dt>
              <dd class="num">{{ l.waiting }}</dd>
            </div>
            <div>
              <dt>Ожидание</dt>
              <dd class="num">{{ sec(l.avg_wait_s) }}</dd>
            </div>
            <div>
              <dt>Обработка</dt>
              <dd class="num">{{ sec(l.avg_run_s) }}</dd>
            </div>
            <div>
              <dt>За час</dt>
              <dd class="num">
                {{ l.done_1h }}<span v-if="l.failed_1h" class="bad"> · {{ l.failed_1h }} сбоев</span>
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section class="card block">
        <h2 class="label">Задачи сейчас · {{ data.jobs.length }}</h2>
        <p v-if="!data.jobs.length" class="note">Очередь пуста — все задачи выполнены.</p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Задача</th>
                <th>Покупатель</th>
                <th>Тариф</th>
                <th>Статус</th>
                <th class="r">Ждала</th>
                <th class="r">Выполняется</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(j, i) in data.jobs" :key="i">
                <td>{{ j.title }}</td>
                <td class="mail">{{ j.email }}</td>
                <td>{{ PLAN[j.plan] ?? j.plan }}</td>
                <td>
                  <span class="st" :class="j.status">{{
                    j.status === 'running' ? 'выполняется' : `в очереди, ${j.position}-я`
                  }}</span>
                </td>
                <td class="r num">{{ sec(j.waited_s) }}</td>
                <td class="r num">{{ j.running_s ? sec(j.running_s) : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
@import './panel.css';

.panel.wide {
  max-width: 1100px;
}

.loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-3);
}

.lanes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.lane {
  display: grid;
  gap: 12px;
  padding: 16px 18px;
}

.lh {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.busy {
  font-size: 20px;
  font-weight: 500;
}

.busy.hot {
  color: var(--warn);
}

.slots {
  display: flex;
  gap: 4px;
}

.slots i {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: var(--panel-2);
}

.slots i.on {
  background: var(--lime);
}

dl {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
  margin: 0;
}

dt {
  font-size: 11.5px;
  color: var(--ink-3);
}

dd {
  margin: 2px 0 0;
  font-size: 14px;
  font-weight: 500;
}

.bad {
  color: var(--bad);
  font-weight: 400;
  font-size: 12px;
}

.block {
  display: grid;
  gap: 12px;
  padding: 20px 22px;
}

.block h2 {
  margin: 0;
}

.note {
  margin: 0;
  font-size: 13px;
  color: var(--ink-3);
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}

thead th {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--ink-3);
}

.r {
  text-align: right;
}

.mail {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.st {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11.5px;
  background: var(--panel-2);
}

.st.running {
  background: var(--lime);
  color: var(--on-tile);
}
</style>
