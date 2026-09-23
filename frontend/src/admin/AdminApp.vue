<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, type Component } from 'vue'
import { ExternalLink, Image as ImageIcon, LayoutTemplate, LogOut, Sparkles } from 'lucide-vue-next'
import Logo from '../components/Logo.vue'
import ThemeToggle from '../components/ThemeToggle.vue'
import ToastMessage from '../components/ToastMessage.vue'
import LoginView from './LoginView.vue'
import LandingPanel from './LandingPanel.vue'
import ExamplesPanel from './ExamplesPanel.vue'
import ExpertPanel from './ExpertPanel.vue'
import { adminApi, auth, setToken } from './adminApi'
import { TOAST_MS } from '../lib/constants'
import type { AdminSettings } from '../lib/types'

type Tab = 'landing' | 'examples' | 'expert'
const tabs: { id: Tab; title: string; icon: Component }[] = [
  { id: 'landing', title: 'Главная', icon: LayoutTemplate },
  { id: 'examples', title: 'Примеры', icon: ImageIcon },
  { id: 'expert', title: 'Экспертный разбор', icon: Sparkles },
]

function tabFromHash(): Tab {
  const id = location.hash.slice(1)
  return tabs.find((t) => t.id === id)?.id ?? 'landing'
}

const tab = ref<Tab>(tabFromHash())
const data = ref<AdminSettings | null>(null)
const error = ref('')
const toast = ref('')
let timer = 0

// вкладка живёт в адресе: её можно открыть ссылкой, а правка #хеша вручную тоже переключает её
watch(tab, (t) => {
  if (location.hash !== `#${t}`) history.replaceState(null, '', `#${t}`)
})
const onHashChange = () => (tab.value = tabFromHash())

async function reload() {
  try {
    data.value = await adminApi.settings()
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  }
}

function notify(msg: string) {
  toast.value = msg
  clearTimeout(timer)
  timer = window.setTimeout(() => (toast.value = ''), TOAST_MS)
}

watch(
  () => auth.token,
  (t) => (t ? reload() : (data.value = null)),
)
onMounted(() => {
  document.title = 'Админ-панель — Monster Lab'
  window.addEventListener('hashchange', onHashChange)
  if (auth.token) reload()
})
onUnmounted(() => {
  window.removeEventListener('hashchange', onHashChange)
  clearTimeout(timer)
})
</script>

<template>
  <LoginView v-if="!auth.token" />
  <div v-else class="admin">
    <aside class="side">
      <div class="brand">
        <Logo :size="30" :wordmark="false" />
        <div>
          <strong>Monster Lab</strong>
          <span class="num">админ-панель</span>
        </div>
      </div>
      <nav>
        <button
          v-for="t in tabs"
          :key="t.id"
          :class="{ on: tab === t.id }"
          :aria-current="tab === t.id ? 'page' : undefined"
          @click="tab = t.id"
        >
          <component :is="t.icon" :size="16" />{{ t.title }}
        </button>
      </nav>
      <div class="foot">
        <a class="btn ghost sm" href="/" target="_blank"><ExternalLink :size="14" /> Открыть сайт</a>
        <div class="row">
          <button class="btn ghost sm" @click="setToken('')"><LogOut :size="14" /> Выйти</button>
          <ThemeToggle class="sm" :size="15" />
        </div>
      </div>
    </aside>

    <main class="content">
      <p v-if="error" class="err load-err">{{ error }}</p>
      <template v-if="data">
        <LandingPanel v-if="tab === 'landing'" :data="data" @saved="notify" />
        <ExamplesPanel v-else-if="tab === 'examples'" :data="data" @changed="reload" @notify="notify" />
        <ExpertPanel v-else :data="data" @notify="notify" @changed="reload" />
      </template>
    </main>

    <ToastMessage :message="toast" />
  </div>
</template>

<style scoped>
@import './panel.css';

.admin {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  height: 100vh;
  height: 100dvh;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 20px 14px;
  border-right: 1px solid var(--line);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 6px;
}

.brand div {
  display: grid;
  line-height: 1.15;
}

.brand strong {
  font-size: 15px;
  font-weight: 500;
  letter-spacing: -0.02em;
}

.brand span {
  font-size: 10.5px;
  color: var(--ink-3);
}

nav {
  display: grid;
  gap: 2px;
}

nav button {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 36px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  background: none;
  color: var(--ink-2);
  font-size: 13.5px;
  font-weight: 500;
  text-align: left;
}

nav button:hover {
  background: var(--panel-2);
  color: var(--ink);
}

nav button.on {
  background: var(--panel);
  color: var(--ink);
  box-shadow: 0 0 0 1px var(--line);
}

.foot {
  margin-top: auto;
  display: grid;
  gap: 4px;
}

.foot .row {
  display: flex;
  justify-content: space-between;
}

.foot a {
  text-decoration: none;
  justify-content: flex-start;
}

.content {
  overflow-y: auto;
  min-width: 0;
}

.load-err {
  margin: 20px;
}

@media (max-width: 800px) {
  .admin {
    grid-template-columns: 1fr;
    height: auto;
  }
  .side {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
}
</style>
