<script setup lang="ts">
import UploadButton from './UploadButton.vue'
import ExamplesGallery from './ExamplesGallery.vue'
import Steps from './Steps.vue'
import type { Landing } from '../../lib/types'

defineProps<{ l: Landing }>()
</script>

<template>
  <div class="editorial">
    <section class="hero rise">
      <span class="label">{{ l.eyebrow }}</span>
      <h1>
        {{ l.title }}
        <em v-if="l.title_muted">{{ l.title_muted }}</em>
      </h1>
      <div class="row">
        <p class="lead">{{ l.lead }}</p>
        <UploadButton :label="l.cta" />
      </div>
    </section>
    <Steps :steps="l.steps" />
    <ExamplesGallery />
  </div>
</template>

<style scoped>
.editorial {
  flex: 1;
  overflow-y: auto;
  display: grid;
  align-content: start;
  gap: 56px;
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
  padding: clamp(40px, 9vh, 110px) clamp(20px, 5vw, 64px) 64px;
}

h1 {
  margin: 16px 0 36px;
  max-width: 1100px;
  font-size: clamp(40px, 6.4vw, 96px);
  line-height: 0.98;
  font-weight: 300;
  letter-spacing: -0.045em;
}

h1 em {
  display: block;
  font-style: normal;
  color: var(--ink-3);
}

.row {
  display: grid;
  grid-template-columns: minmax(0, 560px) auto;
  justify-content: space-between;
  align-items: end;
  gap: 40px;
}

.lead {
  margin: 0;
  font-size: 17px;
  line-height: 1.55;
  color: var(--ink-2);
}

@media (max-width: 900px) {
  .row {
    grid-template-columns: 1fr;
    gap: 24px;
  }
}
</style>
