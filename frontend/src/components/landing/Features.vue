<script setup lang="ts">
import { FolderOpen, ScanEye, Sparkles, Users, Search, Layers } from 'lucide-vue-next'
import { addFiles } from '../../store'
import { useFilePicker } from '../../lib/useFilePicker'

const pick = useFilePicker((files) => addFiles(files))
const features = [
  {
    icon: ScanEye,
    title: 'Визуальный разбор',
    text: 'Разбор композиции и надписей с рекомендациями по улучшению.',
  },
  {
    icon: Search,
    title: 'Подбор конкурентов',
    text: 'Поиск обложек на Wildberries для сравнения с вашей карточкой.',
  },
  {
    icon: Layers,
    title: 'Тест на полке',
    text: 'Проверка заметности среди конкурентов на разных местах в выдаче.',
  },
  {
    icon: Users,
    title: 'Выбор покупателя',
    text: 'Сравнение до четырёх обложек: прогноз выбора и причины оценки.',
  },
  {
    icon: Sparkles,
    title: 'Улучшение обложки',
    text: 'Новый вариант по результатам разбора. Можно скачать или сравнить с исходным.',
  },
  {
    icon: FolderOpen,
    title: 'Личный кабинет',
    text: 'Ваши обложки и результаты проверок. Можно открыть, скачать или удалить.',
  },
]
</script>

<template>
  <section class="features" aria-labelledby="features-title">
    <div class="heading">
      <span class="label">Возможности</span>
      <h2 id="features-title" class="display">Проверка, сравнение и улучшение обложек</h2>
      <p>Выберите нужную функцию после загрузки.</p>
    </div>
    <div class="feature-grid">
      <article v-for="(feature, i) in features" :key="feature.title">
        <span class="icon" :class="`tone-${i % 3}`"
          ><component :is="feature.icon" :size="22" aria-hidden="true"
        /></span>
        <h3>{{ feature.title }}</h3>
        <p>{{ feature.text }}</p>
      </article>
    </div>
    <div class="start">
      <div>
        <h3>Загрузите свои обложки</h3>
        <p>До четырёх картинок: JPG, PNG или WebP.</p>
      </div>
      <button type="button" class="btn primary" @click="pick()">Загрузить обложки</button>
    </div>
  </section>
</template>

<style scoped>
.features {
  display: grid;
  gap: 24px;
}
.heading {
  max-width: 720px;
}
h2 {
  margin: 12px 0;
  font-size: clamp(30px, 3vw, 44px);
  line-height: 1.12;
}
p {
  margin: 0;
  color: var(--ink-2);
  font-size: 15px;
  line-height: 1.5;
}
.heading > p {
  font-size: 17px;
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
article {
  padding: 24px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel);
}
.icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  color: var(--on-tile);
}
.tone-0 {
  background: var(--lilac);
}
.tone-1 {
  background: var(--mint);
}
.tone-2 {
  background: var(--lime);
}
h3 {
  margin: 18px 0 8px;
  font-size: 20px;
  font-weight: 500;
  letter-spacing: -0.025em;
}
.start {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 28px;
  border-radius: 12px;
  background: var(--panel-2);
}
.start h3 {
  margin-top: 0;
}
.start .btn {
  flex-shrink: 0;
  min-height: 42px;
}
@media (max-width: 900px) {
  .feature-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 560px) {
  .feature-grid {
    grid-template-columns: 1fr;
  }
  .start {
    align-items: stretch;
    flex-direction: column;
    padding: 24px;
  }
}
</style>
