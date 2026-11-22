<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { refreshMe } from '../lib/account'
import { session } from '../lib/session'
import Logo from '../components/Logo.vue'
import PartnerView from './PartnerView.vue'
import RulesView from './RulesView.vue'
import WbView from './WbView.vue'
const tabs = [
  { id: 'rules', title: 'Правила площадок' },
  { id: 'wb', title: 'Аудит WB' },
  { id: 'partner', title: 'Партнёрам' },
]
const tab = ref('rules')
function select() {
  tab.value = tabs.find((t) => t.id === location.hash.slice(1))?.id || 'rules'
  document.title = tabs.find((t) => t.id === tab.value)!.title + ' — MonStoreLab'
}
onMounted(() => {
  void refreshMe()
  select()
  window.addEventListener('hashchange', select)
})
onUnmounted(() => window.removeEventListener('hashchange', select))
</script>
<template>
  <main class="studio">
    <header>
      <a href="/" aria-label="MonStoreLab, главная"><Logo :size="32" /></a><a href="/articles">Статьи</a>
    </header>
    <nav aria-label="Инструменты продавца">
      <a v-for="t in tabs" :key="t.id" :href="'#' + t.id" :aria-current="tab === t.id ? 'page' : undefined">{{
        t.title
      }}</a>
    </nav>
    <section v-if="!session.token">
      <h1>Инструменты продавца</h1>
      <a class="btn primary" :href="'/?studio=' + tab">Войти в MonStoreLab</a>
    </section>
    <RulesView v-else-if="tab === 'rules'" /><WbView v-else-if="tab === 'wb'" /><PartnerView v-else />
  </main>
</template>
<style>
body:has(.studio) {
  overflow: auto;
}
.studio {
  font-family: Onest, system-ui, sans-serif;
  max-width: 960px;
  margin: auto;
  padding: 24px clamp(16px, 4vw, 48px) 80px;
  color: var(--ink);
}
.studio header,
.studio nav,
.studio .pager {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
}
.studio header {
  justify-content: space-between;
}
.studio nav {
  margin: 24px 0;
  border-bottom: 1px solid var(--line);
  gap: 4px;
}
.studio nav a {
  padding: 12px 14px;
  color: var(--ink-2);
  text-decoration: none;
}
.studio nav a[aria-current] {
  color: var(--ink);
  border-bottom: 3px solid var(--accent, var(--ink));
}
.studio section {
  max-width: 780px;
}
.studio h1 {
  font-size: clamp(28px, 5vw, 44px);
  line-height: 1.1;
  letter-spacing: -0.04em;
  margin: 28px 0 14px;
}
.studio h2 {
  font-size: 24px;
}
.studio p,
.studio li {
  line-height: 1.55;
}
.studio .field,
.studio form {
  display: grid;
  gap: 10px;
}
.studio form,
.studio .result {
  margin: 22px 0;
  padding: clamp(14px, 3vw, 28px);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel);
}
.studio .btn {
  justify-self: start;
  white-space: normal;
}
.studio textarea {
  height: auto;
  min-height: 72px;
  resize: vertical;
}
.studio small {
  display: block;
  color: var(--ink-2);
}
.studio article {
  padding: 16px 0;
  border-bottom: 1px solid var(--line);
  overflow-wrap: anywhere;
}
.studio .totals {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 18px 0;
}
.totals span {
  padding: 12px;
  background: var(--panel-2);
  border-radius: 10px;
}
.totals b {
  display: block;
  font-size: 24px;
}
.studio .pager {
  margin-top: 16px;
}
.studio a {
  color: inherit;
}
</style>
