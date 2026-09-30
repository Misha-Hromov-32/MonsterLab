<script setup lang="ts">
import { computed, type Component } from 'vue'
import DesignEditorial from './DesignEditorial.vue'
import DesignSplit from './DesignSplit.vue'
import DesignFeed from './DesignFeed.vue'
import { DEFAULT_LANDING } from './defaults'
import { site } from '../../store'
import type { Design } from '../../lib/types'

const DESIGNS: Record<Design, Component> = { editorial: DesignEditorial, split: DesignSplit, feed: DesignFeed }

// ?design=feed — предпросмотр варианта из админки без сохранения.
// hasOwn, а не in: иначе ?design=toString подхватит поле прототипа.
const param = new URLSearchParams(location.search).get('design')
const override = param && Object.hasOwn(DESIGNS, param) ? (param as Design) : null

// Пока сервер не ответил (не дольше 10 секунд), держим пустое место высотой в страницу — иначе мелькнул бы
// вариант по умолчанию и сменился настроенным. Если ответа нет, показываем тексты по умолчанию.
const landing = computed(() => site.data?.landing ?? DEFAULT_LANDING)
const design = computed(() => DESIGNS[override ?? landing.value.design] ?? DesignSplit)
</script>

<template>
  <div v-if="!site.loaded" class="wait" aria-busy="true" />
  <div v-else class="landing-page">
    <component :is="design" :l="landing" />
    <footer class="legal-foot">
      <span>© Monster Lab</span>
      <a href="/legal#terms">Пользовательское соглашение</a>
      <a href="/legal#privacy">Политика конфиденциальности</a>
    </footer>
  </div>
</template>

<style scoped>
.landing-page {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.wait {
  flex: 1 0 auto;
  min-height: calc(100dvh - 64px);
}

.legal-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 20px;
  padding: 20px 16px 28px;
  justify-content: center;
  border-top: 1px solid var(--line);
  font-size: 12.5px;
  color: var(--ink-3);
}

.legal-foot a {
  color: var(--ink-2);
  text-decoration: none;
}

.legal-foot a:hover {
  color: var(--ink);
  text-decoration: underline;
  text-underline-offset: 3px;
}
</style>
