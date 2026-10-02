<script setup lang="ts">
import BrandMark from './BrandMark.vue'
import { WORDMARK } from '../lib/brand'

// Логотип MonStoreLab. С wordmark — строка «MON STORE LAB» (высота size × 0.62, чтобы вместе с подписью
// занимать ту же высоту, что и знак); без него — только знак «O с рожками» (админка, узкие места).
const props = withDefaults(defineProps<{ size?: number; wordmark?: boolean; sub?: string }>(), {
  size: 32,
  wordmark: true,
})
</script>

<template>
  <span class="logo" :aria-label="props.wordmark ? undefined : 'MonStoreLab'">
    <template v-if="wordmark">
      <span class="words">
        <svg
          class="wm"
          :viewBox="WORDMARK.viewBox"
          :height="Math.round(size * 0.62)"
          role="img"
          aria-label="MonStoreLab"
        >
          <path :d="WORDMARK.d" fill-rule="evenodd" />
        </svg>
        <span v-if="sub" class="sub">{{ sub }}</span>
      </span>
    </template>
    <BrandMark v-else :size="size" />
  </span>
</template>

<style scoped>
.logo {
  display: inline-flex;
  align-items: center;
  color: var(--ink);
}

.words {
  display: grid;
  gap: 4px;
  justify-items: start;
}

.wm {
  display: block;
  width: auto;
  fill: var(--brand);
}

.sub {
  font-size: 11px;
  line-height: 1;
  color: var(--ink-3);
  letter-spacing: -0.01em;
  white-space: nowrap;
}
</style>
