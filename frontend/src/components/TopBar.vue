<script setup lang="ts">
import { computed, type Component } from 'vue'
import { Columns3, Eye, LayoutGrid, Plus, Upload } from 'lucide-vue-next'
import Logo from './Logo.vue'
import ThemeToggle from './ThemeToggle.vue'
import AccountButton from './AccountButton.vue'
import { addFiles, featuredExample, loadExample, paidAvailable, ready, resetAll, state } from '../store'
import { useFilePicker } from '../lib/useFilePicker'
import type { View } from '../lib/types'

interface Tab {
  id: View
  title: string
  hint: string
  icon: Component
  disabled: boolean
  count?: number
}

const working = computed(() => state.variants.length > 0)

// подсказка — и в title, и в aria-describedby: причина недоступности вкладки не должна жить только в тултипе
const tabs = computed<Tab[]>(() => [
  {
    id: 'analyze',
    title: 'Разбор',
    icon: Eye,
    hint: 'Одна обложка подробно: карта внимания и что исправить',
    disabled: false,
  },
  {
    id: 'compare',
    title: 'Сравнение',
    icon: Columns3,
    hint: ready.value.length < 2 ? 'Добавьте второй вариант, чтобы сравнить' : 'Все варианты рядом и таблица метрик',
    disabled: ready.value.length < 2,
    count: ready.value.length >= 2 ? ready.value.length : undefined,
  },
  {
    id: 'shelf',
    title: 'Полка',
    icon: LayoutGrid,
    hint: ready.value.length
      ? 'Заметят ли обложку среди конкурентов в выдаче'
      : 'Дождитесь, пока закончится анализ обложки',
    disabled: !ready.value.length,
  },
])

// навигация главной — прокрутка к разделам
function go(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const pick = useFilePicker((files) => addFiles(files))

// на широком экране главная прокручивается внутри себя (корень варианта главной — прямой потомок .main),
// на телефоне — вся страница; наверх возвращаем оба
function toTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
  document.querySelector('.main > *')?.scrollTo({ top: 0, behavior: 'smooth' })
}

function home() {
  if (!working.value) return toTop()
  // спрашиваем, только когда есть что терять
  if (confirm('Начать новый анализ? Загруженные обложки и все результаты будут удалены.')) resetAll()
}
</script>

<template>
  <header class="top" :class="{ working }">
    <button type="button" class="brand" :title="working ? 'Новый анализ' : 'Monster Lab'" @click="home">
      <Logo :size="32" sub="тест обложек для маркетплейсов" />
    </button>

    <nav v-if="!working" class="links" aria-label="Разделы">
      <button type="button" @click="go('how')">Как это работает</button>
      <button type="button" @click="go('examples')">Примеры</button>
    </nav>

    <nav v-else class="tabs" aria-label="Режим">
      <button
        v-for="t in tabs"
        :key="t.id"
        type="button"
        class="tab"
        :class="{ on: state.view === t.id }"
        :aria-current="state.view === t.id ? 'page' : undefined"
        :aria-describedby="`tab-hint-${t.id}`"
        :disabled="t.disabled"
        :title="t.hint"
        @click="state.view = t.id"
      >
        <component :is="t.icon" :size="16" aria-hidden="true" />
        {{ t.title }}
        <span v-if="t.count" class="count">{{ t.count }}</span>
      </button>
      <span v-for="t in tabs" :id="`tab-hint-${t.id}`" :key="`hint-${t.id}`" hidden>{{ t.hint }}</span>
    </nav>

    <div class="actions">
      <span v-if="state.healthError" class="status" role="status"><i class="dot bad" />Сервис недоступен</span>
      <ThemeToggle />
      <!-- аккаунт нужен только для платных функций: если на сервере их нет, кнопку не показываем -->
      <AccountButton v-if="paidAvailable" />
      <template v-if="!working">
        <button v-if="featuredExample" type="button" class="btn pill hide-sm" @click="loadExample(featuredExample)">
          Открыть пример
        </button>
        <button type="button" class="btn primary" @click="pick()">
          <Upload :size="15" aria-hidden="true" /> <span class="hide-xs">Загрузить обложки</span>
        </button>
      </template>
      <button v-else type="button" class="btn pill" title="Сбросить и начать заново" @click="home">
        <Plus :size="15" aria-hidden="true" /> <span class="hide-xs">Новый анализ</span>
      </button>
    </div>
  </header>
</template>

<style scoped>
.top {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 24px;
  height: 64px;
  padding: 0 16px 0 20px;
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: saturate(1.4) blur(10px);
  position: relative;
  z-index: 20;
}

.top.working {
  /* бренд по ширине левой панели: колонка = панель минус левый отступ шапки */
  grid-template-columns: calc(var(--rail-w) - 20px) 1fr auto;
}

.brand {
  justify-self: start;
  padding: 4px;
  margin-left: -4px;
  border: 0;
  border-radius: 10px;
  background: none;
  text-align: left;
}

.brand:hover {
  background: var(--panel-2);
}

/* главная */
.links {
  display: flex;
  justify-content: center;
  gap: 4px;
}

.links button {
  height: 36px;
  padding: 0 14px;
  border: 0;
  border-radius: 999px;
  background: none;
  font-size: 14.5px;
  letter-spacing: -0.02em;
  color: var(--ink-2);
}

.links button:hover {
  background: var(--panel-2);
  color: var(--ink);
}

/* рабочий режим */
.tabs {
  display: inline-flex;
  justify-self: start;
  gap: 2px;
  padding: 3px;
  border-radius: 12px;
  background: var(--panel-2);
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 14px;
  border: 0;
  border-radius: 9px;
  background: none;
  color: var(--ink-2);
  font-size: 14px;
  letter-spacing: -0.02em;
  transition:
    background 0.15s,
    color 0.15s;
}

.tab:hover:not(:disabled) {
  color: var(--ink);
}

.tab.on {
  background: var(--panel);
  color: var(--ink);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.06),
    0 0 0 1px var(--line);
}

.tab:disabled {
  opacity: 0.4;
  cursor: default;
}

.count {
  display: grid;
  place-items: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--lime);
  color: var(--on-tile);
  font-size: 11.5px;
  font-weight: 500;
}

/* справа */
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.actions .btn:not(.icon) {
  height: 38px;
  padding: 0 16px;
  font-size: 14px;
  letter-spacing: -0.02em;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 99px;
  font-size: 12px;
  color: var(--ink-2);
  white-space: nowrap;
}

@media (max-width: 1100px) {
  .top.working {
    grid-template-columns: auto 1fr auto;
  }
  .brand :deep(.sub) {
    display: none;
  }
}

@media (max-width: 900px) {
  .top,
  .top.working {
    grid-template-columns: auto 1fr;
    height: auto;
    padding: 10px 12px;
    row-gap: 10px;
  }
  .links {
    display: none;
  }
  .tabs {
    grid-column: 1 / -1;
    grid-row: 2;
    justify-self: stretch;
  }
  .tab {
    flex: 1;
    justify-content: center;
    padding: 0 8px;
  }
  .actions {
    justify-self: end;
  }
  .hide-sm {
    display: none;
  }
}

/* с кнопкой входа подписи не помещаются раньше — оставляем иконки */
@media (max-width: 520px) {
  .hide-xs {
    display: none;
  }
}
</style>
