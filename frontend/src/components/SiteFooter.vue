<script setup lang="ts">
import { onMounted } from 'vue'
import { legal, loadLegal, ogrnLabel } from '../lib/legal'

// Подвал: документы и реквизиты исполнителя — продавец услуг обязан раскрыть их на сайте.
onMounted(loadLegal)
const year = new Date().getFullYear()
</script>

<template>
  <footer class="site-foot">
    <nav class="docs" aria-label="Документы">
      <a href="/legal#terms">Пользовательское соглашение</a>
      <a href="/legal#privacy">Политика обработки персональных данных</a>
      <a href="/legal#consent">Согласие на обработку данных</a>
      <a href="/legal#cookies">Cookie</a>
    </nav>
    <p v-if="legal.data?.name || legal.data?.operator" class="req">
      <template v-if="legal.data.name">
        <span>{{ legal.data.name }}</span>
        <span v-if="legal.data.inn">ИНН {{ legal.data.inn }}</span>
        <span v-if="legal.data.ogrn">{{ ogrnLabel }} {{ legal.data.ogrn }}</span>
        <span v-if="legal.data.address">{{ legal.data.address }}</span>
      </template>
      <span v-else>{{ legal.data.operator }}</span>
      <a v-if="legal.data.email" :href="`mailto:${legal.data.email}`">{{ legal.data.email }}</a>
    </p>
    <p class="copy">© {{ year }} MonStoreLab</p>
  </footer>
</template>

<style scoped>
.site-foot {
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 24px 16px 28px;
  border-top: 1px solid var(--line);
  font-size: 12.5px;
  color: var(--ink-3);
  text-align: center;
}

.docs,
.req {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px 18px;
  margin: 0;
}

.req span + span::before,
.req span + a::before {
  content: '·';
  margin-right: 18px;
  margin-left: -10px;
  color: var(--line-strong);
}

a {
  color: var(--ink-2);
  text-decoration: none;
}

a:hover {
  color: var(--ink);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.req {
  color: var(--ink-2);
}

.copy {
  margin: 0;
}
</style>
