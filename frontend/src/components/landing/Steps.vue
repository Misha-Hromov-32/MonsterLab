<script setup lang="ts">
defineProps<{ steps: { title: string; text: string }[] }>()
</script>

<template>
  <ol id="how" class="steps">
    <li v-for="(s, i) in steps" :key="i">
      <span class="n">{{ i + 1 }}</span>
      <h3 class="display">{{ s.title }}</h3>
      <p>{{ s.text }}</p>
    </li>
  </ol>
</template>

<style scoped>
#how {
  scroll-margin-top: 24px;
}

.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

li {
  padding: 22px 22px 24px;
  border-radius: 10px;
  background: var(--panel-2);
}

.n {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  color: var(--on-tile);
  font-size: 14px;
  font-weight: 500;
}

/* цвета номеров чередуются по кругу */
li:nth-child(3n + 1) .n {
  background: var(--lime);
}

li:nth-child(3n + 2) .n {
  background: var(--lilac);
}

li:nth-child(3n) .n {
  background: var(--mint);
}

h3 {
  margin: 18px 0 8px;
  font-size: 24px;
  line-height: 1.15;
}

p {
  margin: 0;
  font-size: 15px;
  line-height: 1.45;
  letter-spacing: -0.015em;
  color: var(--ink-2);
}

@media (max-width: 800px) {
  .steps {
    grid-template-columns: 1fr;
  }
}
</style>
