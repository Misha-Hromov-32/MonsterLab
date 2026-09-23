<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'
import { loadExample, site } from '../../store'
import { plural } from '../../lib/format'
</script>

<template>
  <section v-if="site.data?.examples.length" id="examples" class="gallery">
    <div class="head">
      <h2 class="display">Примеры</h2>
      <span class="sub">Откройте готовый набор обложек, чтобы посмотреть, как всё работает</span>
    </div>
    <div class="cards">
      <!-- кликабельна вся карточка: кнопка «Открыть» растянута псевдоэлементом на всю площадь -->
      <article v-for="ex in site.data.examples" :key="ex.id" class="ex">
        <div class="covers">
          <img v-for="v in ex.variants.slice(0, 4)" :key="v.id" :src="v.url" alt="" loading="lazy" />
        </div>
        <div class="body">
          <h3>{{ ex.title }}</h3>
          <p v-if="ex.description">{{ ex.description }}</p>
          <span class="meta num">
            {{ ex.variants.length }} {{ plural(ex.variants.length, ['вариант', 'варианта', 'вариантов']) }}
            <template v-if="ex.competitors.length">
              · {{ ex.competitors.length }}
              {{ plural(ex.competitors.length, ['конкурент', 'конкурента', 'конкурентов']) }}
            </template>
          </span>
        </div>
        <button type="button" class="go" :aria-label="`Открыть пример «${ex.title}»`" @click="loadExample(ex)">
          Открыть <ArrowRight :size="15" aria-hidden="true" />
        </button>
      </article>
    </div>
  </section>
</template>

<style scoped>
#examples {
  scroll-margin-top: 24px;
}

.gallery {
  display: grid;
  gap: 18px;
}

.head h2 {
  margin: 0;
  font-size: 32px;
}

.head {
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
}

.sub {
  font-size: 13px;
  color: var(--ink-3);
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.ex {
  position: relative;
  display: grid;
  gap: 14px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--panel);
  cursor: pointer;
  transition:
    border-color 0.15s,
    transform 0.15s,
    box-shadow 0.2s;
}

.ex:hover {
  border-color: var(--line-strong);
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.covers {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}

.covers img {
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
  border-radius: 7px;
  background: var(--sunken);
}

.body {
  display: grid;
  gap: 4px;
}

h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 300;
  letter-spacing: -0.04em;
}

p {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}

.meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--ink-3);
}

.go {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--ink-2);
  background: none;
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
}

.go::after {
  content: '';
  position: absolute;
  inset: 0;
}

.ex:hover .go {
  background: var(--lime);
  border-color: var(--lime);
  color: var(--on-tile);
}
</style>
