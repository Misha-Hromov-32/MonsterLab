<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus, Replace, RotateCcw, X, AlertCircle } from 'lucide-vue-next'
import { addFiles, analyze, expertEnabled, removeVariant, state } from '../store'
import { MAX_VARIANTS } from '../lib/constants'
import { KEYS, type Key } from '../lib/types'
import { baseName, tone } from '../lib/format'
import { useFilePicker } from '../lib/useFilePicker'

const extra = ref(false)

const slots = computed(() => KEYS.map((key) => ({ key, v: state.variants.find((x) => x.key === key) })))

// key задан — заменяем файл в этом слоте (один файл), иначе добавляем новые варианты
function pick(key?: Key) {
  useFilePicker((files) => addFiles(files, key))({ multiple: !key })
}

function select(key: Key) {
  state.selected = key
  if (state.view !== 'analyze') state.view = 'analyze'
}
</script>

<template>
  <aside class="rail scroll-y">
    <section>
      <div class="head">
        <span class="label">Варианты</span>
        <span class="label num">{{ state.variants.length }}/{{ MAX_VARIANTS }}</span>
      </div>

      <ul class="slots">
        <li v-for="{ key, v } in slots" :key="key">
          <div v-if="v" class="slot filled" :class="{ on: state.selected === key && state.view === 'analyze' }">
            <!-- кнопки инструментов — соседи, а не потомки: вложенные кнопки недоступны с клавиатуры -->
            <button
              type="button"
              class="open"
              :aria-current="state.selected === key && state.view === 'analyze' ? 'true' : undefined"
              @click="select(key)"
            >
              <span class="thumb">
                <img :src="v.url" alt="" />
                <span class="key num">{{ key }}</span>
              </span>
              <span class="meta">
                <span class="fname" :title="v.name">{{ baseName(v.name) }}</span>
                <span v-if="v.status === 'loading'" class="state num loading">анализ…</span>
                <span v-else-if="v.status === 'error'" class="state num err"><AlertCircle :size="12" /> ошибка</span>
                <span v-else-if="v.analysis" class="state num">
                  <i class="dot" :class="tone(v.analysis.index)" />
                  индекс <b class="num">{{ v.analysis.index }}</b>
                </span>
              </span>
            </button>
            <div class="tools">
              <button
                v-if="v.status === 'error'"
                class="btn ghost sm icon"
                title="Повторить анализ"
                :aria-label="`Повторить анализ варианта ${key}`"
                @click="analyze(v)"
              >
                <RotateCcw :size="14" />
              </button>
              <button
                class="btn ghost sm icon"
                title="Заменить файл"
                :aria-label="`Заменить файл варианта ${key}`"
                @click="pick(key)"
              >
                <Replace :size="14" />
              </button>
              <button
                class="btn ghost sm icon"
                title="Удалить"
                :aria-label="`Удалить вариант ${key}`"
                @click="removeVariant(key)"
              >
                <X :size="15" />
              </button>
            </div>
          </div>
          <button v-else class="slot empty" @click="pick()">
            <span class="key num">{{ key }}</span>
            <span>Добавить вариант</span>
            <Plus :size="16" class="plus" />
          </button>
        </li>
      </ul>
    </section>

    <template v-if="expertEnabled">
      <button class="btn sm more" :aria-expanded="extra" @click="extra = !extra">
        {{ extra ? 'Скрыть данные о товаре' : 'Данные о товаре' }}
      </button>

      <section class="extra" :class="{ open: extra }">
        <div class="head">
          <span class="label">О товаре</span>
          <span class="label hint">чтобы экспертный разбор был точнее</span>
        </div>
        <div class="form">
          <label class="field">
            <span class="flabel">Поисковый запрос</span>
            <input v-model.trim="state.context.query" class="input" maxlength="120" placeholder="термокружка 500 мл" />
          </label>
          <label class="field">
            <span class="flabel">Категория</span>
            <input v-model.trim="state.context.category" class="input" maxlength="80" placeholder="посуда для дома" />
          </label>
          <div class="row">
            <label class="field">
              <span class="flabel">Цена, ₽</span>
              <input
                v-model.trim="state.context.price"
                class="input num"
                maxlength="20"
                inputmode="numeric"
                placeholder="1 290"
              />
            </label>
            <label class="field">
              <span class="flabel">Аудитория</span>
              <input v-model.trim="state.context.audience" class="input" maxlength="80" placeholder="офис, 25–40" />
            </label>
          </div>
        </div>
      </section>
    </template>
  </aside>
</template>

<style scoped>
.rail {
  display: flex;
  flex-direction: column;
  gap: 26px;
  padding: 20px 16px 20px 20px;
  border-right: 1px solid var(--line);
  min-height: 0;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 10px;
}

/* в узкой колонке подсказка не помещается рядом с заголовком — ставим её под ним */
.extra .head {
  display: grid;
  gap: 3px;
  justify-content: start;
}

.hint {
  text-transform: none;
  letter-spacing: 0.01em;
}

.slots {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
}

.slot {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 11px;
  border-radius: var(--radius);
  text-align: left;
}

.slot.filled {
  position: relative;
  border: 1px solid transparent;
  transition:
    background 0.15s,
    border-color 0.15s;
}

.slot.filled:hover {
  background: var(--panel-2);
}

.open {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 6px;
  border: 0;
  border-radius: inherit;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.open:focus-visible {
  outline-offset: 0;
}

.slot.filled.on {
  background: var(--panel);
  border-color: var(--line-strong);
  box-shadow: var(--shadow);
}

.thumb {
  position: relative;
  display: block;
  width: 44px;
  height: 58px;
  flex: none;
  border-radius: 6px;
  overflow: hidden;
  background: var(--sunken);
}

.thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb .key {
  position: absolute;
  left: 3px;
  top: 3px;
  display: grid;
  place-items: center;
  width: 17px;
  height: 17px;
  border-radius: 4px;
  background: var(--ink);
  color: var(--bg);
  font-size: 10.5px;
  font-weight: 600;
}

.meta {
  display: grid;
  gap: 3px;
  min-width: 0;
  flex: 1;
}

.fname {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 500;
}

.state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--ink-2);
}

.state b {
  color: var(--ink);
  font-weight: 600;
}

.state.loading {
  animation: pulse 1.2s ease-in-out infinite;
}

.state.err {
  color: var(--bad);
}

.tools {
  position: absolute;
  right: 4px;
  top: 4px;
  display: flex;
  opacity: 0;
  transition: opacity 0.15s;
  background: var(--panel-2);
  border-radius: 7px;
}

.slot:hover .tools,
.slot:focus-within .tools {
  opacity: 1;
}

.slot.on .tools {
  background: var(--panel);
}

.slot.empty {
  height: 50px;
  padding: 0 12px 0 8px;
  border: 1px dashed var(--line-strong);
  background: transparent;
  color: var(--ink-3);
  font-size: 13px;
  transition:
    color 0.15s,
    border-color 0.15s,
    background 0.15s;
}

.slot.empty .key {
  display: grid;
  place-items: center;
  width: 30px;
  font-size: 12px;
}

.slot.empty .plus {
  margin-left: auto;
}

.slot.empty:hover {
  color: var(--ink);
  border-color: var(--ink-3);
  background: var(--panel);
}

.form {
  display: grid;
  gap: 10px;
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.flabel {
  font-size: 12px;
  color: var(--ink-2);
}

.more {
  display: none;
}

@media (max-width: 900px) {
  .rail {
    min-width: 0; /* иначе лента вариантов распирает страницу вместо своей прокрутки */
    gap: 14px;
    border-right: 0;
    border-bottom: 1px solid var(--line);
    padding: 14px 16px;
  }
  .slots {
    grid-auto-flow: column;
    grid-auto-columns: minmax(236px, 1fr); /* имя варианта помещается рядом с миниатюрой и кнопками */
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: none;
  }
  .tools {
    opacity: 1;
  }
  .slot.filled .tools {
    position: static;
    flex: none;
    background: none;
  }
  .more {
    display: inline-flex;
    justify-self: start;
    align-self: flex-start;
  }
  .extra:not(.open) {
    display: none;
  }
}
</style>
