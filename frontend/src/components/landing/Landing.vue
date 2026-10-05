<script setup lang="ts">
import { computed, type Component } from 'vue'
import DesignBrand from './DesignBrand.vue'
import DesignEditorial from './DesignEditorial.vue'
import DesignSplit from './DesignSplit.vue'
import DesignFeed from './DesignFeed.vue'
import { DEFAULT_LANDING } from './defaults'
import SiteFooter from '../SiteFooter.vue'
import { site } from '../../store'
import type { Design } from '../../lib/types'

const DESIGNS: Record<Design, Component> = {
  brand: DesignBrand,
  editorial: DesignEditorial,
  split: DesignSplit,
  feed: DesignFeed,
}

// ?design=feed — предпросмотр варианта из админки без сохранения.
// hasOwn, а не in: иначе ?design=toString подхватит поле прототипа.
const param = new URLSearchParams(location.search).get('design')
const override = param && Object.hasOwn(DESIGNS, param) ? (param as Design) : null

// Пока сервер не ответил (не дольше 10 секунд), держим пустое место высотой в страницу — иначе мелькнул бы
// вариант по умолчанию и сменился настроенным. Если ответа нет, показываем тексты по умолчанию.
const landing = computed(() => site.data?.landing ?? DEFAULT_LANDING)
const design = computed(() => DESIGNS[override ?? landing.value.design] ?? DesignBrand)
</script>

<template>
  <div v-if="!site.loaded" class="wait" aria-busy="true" />
  <div v-else class="landing-page">
    <component :is="design" :l="landing" />
    <SiteFooter />
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
</style>
