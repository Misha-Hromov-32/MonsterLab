<script setup lang="ts">
import { Moon, Sun } from 'lucide-vue-next'
import { toggleTheme } from '../lib/theme'

withDefaults(defineProps<{ size?: number }>(), { size: 17 })
</script>

<template>
  <!-- обе иконки в разметке, видимую выбирает CSS по data-theme — без мигания при загрузке -->
  <button
    type="button"
    class="btn ghost icon theme"
    aria-label="Сменить тему"
    title="Светлая / тёмная тема"
    @click="toggleTheme"
  >
    <Sun class="sun" :size="size" aria-hidden="true" />
    <Moon class="moon" :size="size" aria-hidden="true" />
  </button>
</template>

<style scoped>
.moon {
  display: none;
}

:root[data-theme='dark'] .sun {
  display: none;
}

:root[data-theme='dark'] .moon {
  display: block;
}

/* главная «лента» всегда тёмная — переключатель там ничего бы не менял */
:root.feed-dark .theme {
  display: none;
}
</style>
