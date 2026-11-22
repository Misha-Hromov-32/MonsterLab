<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Download, FolderOpen, Loader2, Trash2 } from 'lucide-vue-next'
import { navigateCabinet } from '../lib/cabinet'
import { api } from '../api'
import ModalDialog from './ModalDialog.vue'
import { account } from '../lib/account'
import { openSavedCover } from '../store'
import type { SavedCover, SavedCoverDetail } from '../lib/types'

defineProps<{ recent?: boolean }>()
const items = ref<SavedCover[]>([])
const selected = ref<SavedCoverDetail>()
const total = ref(0)
const loading = ref(false)
const busy = ref('')
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await api.library(items.value.length)
    items.value.push(...result.items)
    total.value = result.total
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function preview(item: SavedCover) {
  busy.value = item.id
  error.value = ''
  try {
    selected.value = await api.savedCover(item.id)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
}

function openAnalysis() {
  if (selected.value && openSavedCover(selected.value)) {
    selected.value = undefined
    navigateCabinet(null)
  }
}

async function download(item: SavedCover) {
  busy.value = item.id
  error.value = ''
  try {
    const saved = await api.savedCover(item.id)
    const link = document.createElement('a')
    link.href = saved.image
    link.download = `${item.name.replace(/\.[^.]+$/, '')}.jpg`
    link.click()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
}

async function remove(item: SavedCover) {
  if (!confirm(`Удалить «${item.name}» из личного кабинета?`)) return
  busy.value = item.id
  error.value = ''
  try {
    await api.deleteCover(item.id)
    // Обновляем страницу целиком, чтобы смещение пагинации осталось верным.
    items.value = []
    await load()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="collection">
    <p v-if="!recent" class="intro">
      Ваши загруженные и сгенерированные обложки сохраняются автоматически после успешного анализа или генерации.
      Доступны только вам.
    </p>
    <p v-if="error" class="error" role="alert">
      {{ error }} <button class="btn sm" :disabled="loading" @click="load">Повторить</button>
    </p>
    <div v-if="!loading && !error && !items.length" class="empty-covers">
      <div class="empty-icon"><FolderOpen :size="26" /></div>
      <div>
        <strong>Здесь будут ваши обложки</strong>
        <p>После анализа или генерации результат сохраняется автоматически.</p>
        <a href="/#generator">Создать первую обложку →</a>
      </div>
    </div>
    <div class="covers">
      <article v-for="item in recent ? items.slice(0, 3) : items" :key="item.id" class="cover">
        <button class="preview" :disabled="!!busy" :aria-label="`Открыть ${item.name}`" @click="preview(item)">
          <img :src="item.preview" :alt="item.name" loading="lazy" />
        </button>
        <strong :title="item.name">{{ item.name }}</strong>
        <span class="meta"
          >{{ item.kind === 'generated' ? 'Сгенерирована' : 'Загружена' }} ·
          {{ new Date(item.created_at * 1000).toLocaleDateString('ru-RU') }}</span
        >
        <div class="actions">
          <button class="btn primary sm" :disabled="!!busy" @click="preview(item)">
            <FolderOpen :size="14" /> Открыть
          </button>
          <button class="btn sm icon" :disabled="!!busy" aria-label="Скачать обложку" @click="download(item)">
            <Download :size="14" />
          </button>
          <button class="btn sm icon" :disabled="!!busy" aria-label="Удалить обложку" @click="remove(item)">
            <Trash2 :size="14" />
          </button>
        </div>
      </article>
    </div>
    <p v-if="loading || busy" role="status" class="status"><Loader2 :size="16" class="spin" /> Загружаем…</p>
    <button v-if="!recent && items.length < total" class="btn" :disabled="loading || !!busy" @click="load">
      Показать ещё
    </button>
    <p v-if="!recent && items.length" class="meta">Сохранено {{ total }} из 500 обложек</p>
  </div>
  <ModalDialog v-if="selected" :title="selected.name" wide @close="selected = undefined">
    <img class="full-cover" :src="selected.image" :alt="selected.name" />
    <div class="viewer-actions">
      <a class="lab-secondary" :href="selected.image" :download="selected.name.replace(/\.[^.]+$/, '') + '.jpg'"
        ><Download :size="16" />Скачать</a
      >
      <button
        class="lab-primary"
        :disabled="!selected.analysis && !account.billing?.costs?.analyze"
        @click="openAnalysis"
      >
        {{
          selected.analysis
            ? 'Открыть готовый разбор'
            : account.billing?.costs?.analyze
              ? 'Проверить · ' + account.billing.costs.analyze + ' имп.'
              : 'Проверка недоступна'
        }}
      </button>
    </div>
  </ModalDialog>
</template>

<style scoped>
.full-cover {
  display: block;
  width: 100%;
  max-height: 56dvh;
  object-fit: contain;
  border-radius: 12px;
  background: var(--panel-2);
}
.viewer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.empty-covers {
  padding: clamp(18px, 3vw, 32px);
  display: flex;
  align-items: center;
  gap: 18px;
  background: var(--panel);
  border: 1px dashed var(--line-strong);
  border-radius: 16px;
}
.empty-icon {
  color: var(--brand);
  padding: 14px;
  background: color-mix(in srgb, var(--brand) 8%, var(--panel));
  border-radius: 14px;
  display: grid;
}
.empty-covers strong {
  font-size: 18px;
  white-space: normal;
}
.empty-covers p {
  margin: 5px 0 8px;
  color: var(--ink-2);
  font-size: 14px;
}
.empty-covers a,
.recent-head a {
  color: var(--ink);
  font-size: 14px;
  font-weight: 600;
  text-underline-offset: 4px;
}
.collection {
  display: grid;
  gap: 16px;
}
.empty {
  background: var(--panel-2);
  padding: 30px;
  border-radius: 14px;
}
.empty a {
  display: block;
  color: var(--ink);
  font-weight: 650;
  margin-top: 8px;
}
.intro,
.empty {
  margin: 0;
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.5;
}
.covers {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.cover {
  container-type: inline-size;
  min-width: 0;
  display: grid;
  gap: 8px;
  align-content: start;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px;
  background: var(--panel);
}
.preview {
  border: 0;
  padding: 0;
  border-radius: 8px;
  overflow: hidden;
  background: var(--panel-2);
}
.preview img {
  width: 100%;
  height: 200px;
  object-fit: contain;
  display: block;
}
strong {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta {
  font-size: 12px;
  color: var(--ink-2);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.error {
  color: var(--bad);
}
.status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-2);
}
@container (max-width: 200px) {
  .actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .actions .primary {
    grid-column: 1 / -1;
  }
  .actions .btn {
    width: 100%;
  }
}
@media (max-width: 640px) {
  .actions .btn {
    min-width: 40px;
    min-height: 40px;
  }
  .covers {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .preview img {
    height: 160px;
  }
}
@media (max-width: 380px) {
  .covers {
    grid-template-columns: 1fr;
  }
}
</style>
