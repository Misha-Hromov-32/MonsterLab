<script setup lang="ts">
// Знак: одноглазый монстрик с рожками — «монстр, который следит, куда смотрят».
// Тот же рисунок лежит статикой в public/favicon.svg — при правке контура обновите и его.
// В спокойном виде радужка смещена вбок: глаз «рассматривает» обложку;
// в живом (animated) она стартует из центра, оглядывается и глаз моргает.
const props = withDefaults(defineProps<{ size?: number; animated?: boolean }>(), { size: 32, animated: false })

const BODY =
  'M8 9 L11 3 L14.5 8.2 Q20 7 25.5 8.2 L29 3 L32 9 Q37 12.5 37 20 L37 29 Q37 37 29 37 L11 37 Q3 37 3 29 L3 20 Q3 12.5 8 9 Z'
</script>

<template>
  <svg
    class="monster"
    :class="{ animated: props.animated }"
    :width="size"
    :height="size"
    viewBox="0 0 40 40"
    aria-hidden="true"
  >
    <path class="body" :d="BODY" />
    <g class="lid">
      <circle class="sclera" cx="20" cy="22.5" r="9.5" />
      <!-- позиция радужки — атрибутом, анимация взгляда — CSS-трансформацией вложенной группы -->
      <g :transform="animated ? 'translate(20 22.5)' : 'translate(22.6 22.5)'">
        <g class="look">
          <circle r="5.6" class="iris" />
          <circle cx="1" r="2.7" class="pupil" />
          <circle cx="2.2" cy="-1.3" r="1" fill="#fff" />
        </g>
      </g>
    </g>
  </svg>
</template>

<style scoped>
.monster {
  flex: none;
}

.body {
  fill: var(--ink);
}

.sclera {
  fill: #fff;
  stroke: var(--on-tile);
  stroke-width: 0;
}

/* в тёмной теме тело светлое — обводим глаз, чтобы белок не сливался с ним */
:root[data-theme='dark'] .sclera,
:root.feed-dark .sclera {
  stroke-width: 1.6;
}

.iris {
  fill: var(--lime);
}

.pupil {
  fill: var(--on-tile);
}

.animated .look {
  animation: look 3.2s ease-in-out infinite;
}

.animated .lid {
  transform-box: fill-box;
  transform-origin: center;
  animation: blink 4.8s infinite;
}

@keyframes look {
  0%,
  12% {
    transform: translate(0, 0);
  }
  22%,
  38% {
    transform: translate(3.6px, -1px);
  }
  48%,
  62% {
    transform: translate(-3.4px, 1.2px);
  }
  72%,
  86% {
    transform: translate(2px, 2.4px);
  }
  100% {
    transform: translate(0, 0);
  }
}

@keyframes blink {
  0%,
  92%,
  100% {
    transform: scaleY(1);
  }
  95% {
    transform: scaleY(0.08);
  }
}
</style>
