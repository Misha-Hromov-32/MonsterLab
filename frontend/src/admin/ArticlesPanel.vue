<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { call } from './adminApi'
import { jsonBody } from '../api'

type Article = {
  id?: number
  version: number
  title: string
  slug: string
  summary: string
  body: string
  published: boolean
}
const blank = (): Article => ({ version: 0, title: '', slug: '', summary: '', body: '', published: false })
const articles = ref<Article[]>([]),
  draft = ref(blank()),
  original = ref(''),
  preview = ref(''),
  busy = ref(false),
  message = ref(''),
  error = ref('')
const dirty = computed(() => original.value && JSON.stringify(draft.value) !== original.value)
function select(article: Article = blank()) {
  if (dirty.value && !confirm('Перейти к другой статье и потерять несохранённые изменения?')) return
  load(article)
}
function load(article: Article) {
  draft.value = { ...article, published: !!article.published }
  original.value = JSON.stringify(draft.value)
  preview.value = ''
  message.value = ''
  error.value = ''
}
async function refresh() {
  articles.value = await call<Article[]>('/api/admin/articles')
}
onMounted(async () => {
  load(blank())
  try {
    await refresh()
  } catch (e) {
    error.value = (e as Error).message
  }
})
async function save() {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const id = draft.value.id
    const saved = await call<Article>(
      '/api/admin/articles' + (id ? '/' + id : ''),
      jsonBody(id ? 'PUT' : 'POST', draft.value),
    )
    load(saved)
    await refresh()
    message.value = saved.published ? 'Статья опубликована' : 'Черновик сохранён'
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
async function showPreview() {
  error.value = ''
  try {
    preview.value = (
      await call<{ html: string }>('/api/admin/articles/preview', jsonBody('POST', { body: draft.value.body }))
    ).html
  } catch (e) {
    error.value = (e as Error).message
  }
}
</script>
<template>
  <div class="panel">
    <header class="ph">
      <div>
        <h1>Статьи</h1>
        <a href="/articles" target="_blank">Открыть журнал</a>
      </div>
      <button class="btn primary" @click="select()">Новая статья</button>
    </header>
    <label class="field"
      >Открыть статью<select
        class="input"
        :value="draft.id || ''"
        @change="select(articles.find((a) => a.id === Number(($event.target as HTMLSelectElement).value)))"
      >
        <option value="">Новая статья</option>
        <option v-for="a in articles" :value="a.id" :key="a.id">
          {{ a.published ? 'Опубликовано' : 'Черновик' }} · {{ a.title }}
        </option>
      </select></label
    >
    <form class="editor" @submit.prevent="save">
      <label class="field">Заголовок<input class="input" v-model.trim="draft.title" maxlength="160" required /></label>
      <label class="field"
        >Адрес после /articles/<input
          class="input"
          v-model.trim="draft.slug"
          placeholder="kak-vybrat-oblozhku"
          pattern="[a-z0-9]+(-[a-z0-9]+)*"
          maxlength="100"
          required
      /></label>
      <label class="field"
        >Краткое описание для читателя и поисковика<textarea
          class="input"
          v-model.trim="draft.summary"
          rows="3"
          maxlength="350"
          required
        ></textarea>
      </label>
      <label class="field"
        >Текст статьи<textarea
          class="input manuscript"
          v-model="draft.body"
          rows="18"
          maxlength="90000"
          required
        ></textarea
        ><small>Подзаголовок начинается с ## и пробела. Для ссылки используйте [текст](https://…).</small></label
      >
      <label><input type="checkbox" v-model="draft.published" /> Публиковать на сайте</label>
      <div class="actions">
        <button class="btn primary" :disabled="busy">Сохранить</button
        ><button type="button" class="btn pill" @click="showPreview">Предпросмотр</button
        ><a
          v-if="draft.id && articles.find((a) => a.id === draft.id)?.published"
          :href="'/articles/' + articles.find((a) => a.id === draft.id)?.slug"
          target="_blank"
          >На сайте</a
        >
      </div>
    </form>
    <p role="alert" v-if="error" class="err">{{ error }}</p>
    <p role="status" v-if="message">{{ message }}</p>
    <article v-if="preview" class="card">
      <h2>{{ draft.title }}</h2>
      <p>{{ draft.summary }}</p>
      <div v-html="preview"></div>
    </article>
  </div>
</template>
<style scoped>
@import './panel.css';
.editor {
  display: grid;
  gap: 16px;
  max-width: 820px;
}
.editor textarea {
  height: auto;
  resize: vertical;
}
.manuscript {
  line-height: 1.6;
}
.card {
  padding: 20px;
}
small {
  color: var(--ink-2);
}
</style>
