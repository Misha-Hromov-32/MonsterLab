<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Download, FolderOpen, Loader2, Trash2 } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
import { api } from '../api'
import { closeDialog } from '../lib/account'
import { openSavedCover } from '../store'
import type { SavedCover } from '../lib/types'

const items = ref<SavedCover[]>([])
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

async function use(item: SavedCover) {
  busy.value = item.id
  error.value = ''
  try {
    const saved = await api.savedCover(item.id)
    if (openSavedCover(saved)) closeDialog()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
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
  <ModalDialog title="Личный кабинет" wide @close="closeDialog">
    <p class="intro">
      Ваши загруженные и сгенерированные обложки сохраняются автоматически после успешного анализа или генерации.
      Доступны только вам.
    </p>
    <p v-if="error" class="error" role="alert">
      {{ error }} <button class="btn sm" :disabled="loading" @click="load">Повторить</button>
    </p>
    <p v-if="!loading && !error && !items.length" class="empty">Здесь пока пусто. Загрузите и проверьте обложку.</p>
    <div class="covers">
      <article v-for="item in items" :key="item.id" class="cover">
        <button class="preview" :disabled="!!busy" :aria-label="`Открыть ${item.name}`" @click="use(item)">
          <img :src="item.preview" :alt="item.name" loading="lazy" />
        </button>
        <strong :title="item.name">{{ item.name }}</strong>
        <span class="meta"
          >{{ item.kind === 'generated' ? 'Сгенерирована' : 'Загружена' }} ·
          {{ new Date(item.created_at * 1000).toLocaleDateString('ru-RU') }}</span
        >
        <div class="actions">
          <button class="btn primary sm" :disabled="!!busy" @click="use(item)">
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
    <button v-if="items.length < total" class="btn" :disabled="loading || !!busy" @click="load">Показать ещё</button>
    <p v-if="items.length" class="meta">Сохранено {{ total }} из 500 обложек</p>
  </ModalDialog>
</template>

<style scoped>
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
  font-size: 11px;
  color: var(--ink-3);
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
@media (max-width: 640px) {
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
