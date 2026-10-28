<script setup lang="ts">
import { computed, ref } from 'vue'
import { Loader2, CheckCircle2 } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
import { api } from '../api'
import { closeLead } from '../store'
import { goal } from '../lib/metrika'

// Форма «Создать карточку»: заявка уходит в бот ВК через бэкенд. Вход в аккаунт не нужен.
const name = ref('')
const phone = ref('')
const description = ref('')
const busy = ref(false)
const error = ref('')
const sent = ref(false)

const canSubmit = computed(() => !busy.value && name.value.trim().length > 0 && phone.value.trim().length >= 5)

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  try {
    await api.lead(name.value.trim(), phone.value.trim(), description.value.trim())
    sent.value = true
    goal('lead')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось отправить заявку. Попробуйте позже.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <ModalDialog :title="sent ? 'Заявка отправлена' : 'Создать карточку'" @close="closeLead">
    <div v-if="sent" class="done">
      <span class="done-icon" aria-hidden="true"><CheckCircle2 :size="22" /></span>
      <p class="done-text">Спасибо! Мы получили заявку и свяжемся с вами по указанному телефону.</p>
      <button class="btn primary wide" type="button" @click="closeLead">Готово</button>
    </div>

    <template v-else>
      <p class="lead">
        Сделаем продающую обложку карточки для вашего товара. Оставьте контакты — мы свяжемся и обсудим детали.
      </p>

      <form class="form" novalidate @submit.prevent="submit">
        <label class="field">
          <span class="flabel">Как вас зовут</span>
          <input v-model="name" class="input" type="text" name="name" autocomplete="name" required data-autofocus />
        </label>
        <label class="field">
          <span class="flabel">Телефон</span>
          <input
            v-model="phone"
            class="input"
            type="tel"
            name="phone"
            autocomplete="tel"
            inputmode="tel"
            placeholder="+7 ..."
            required
          />
        </label>
        <label class="field">
          <span class="flabel">Что за товар и что хотите на обложке</span>
          <textarea
            v-model="description"
            class="input area"
            name="description"
            rows="4"
            maxlength="1000"
            placeholder="Например: беспроводные наушники, нужно показать шумоподавление и время работы"
          />
        </label>

        <p v-if="error" class="err" role="alert">{{ error }}</p>

        <button class="btn primary wide" type="submit" :disabled="!canSubmit">
          <Loader2 v-if="busy" :size="15" class="spin" />
          Отправить заявку
        </button>
        <p class="foot">
          Нажимая «Отправить», вы соглашаетесь на обработку контактов для ответа на заявку (<a
            href="/legal#privacy"
            target="_blank"
            rel="noopener"
            >политика</a
          >).
        </p>
      </form>
    </template>
  </ModalDialog>
</template>

<style scoped>
.lead {
  margin: -4px 0 0;
  font-size: 13.5px;
  line-height: 1.5;
  color: var(--ink-2);
}

.form {
  display: grid;
  gap: 12px;
}

.flabel {
  font-size: 12px;
  color: var(--ink-2);
}

.input {
  height: 40px;
  /* 16px — иначе iOS приближает страницу при фокусе на поле */
  font-size: 16px;
}

.area {
  height: auto;
  padding: 10px 12px;
  line-height: 1.45;
  resize: vertical;
}

.err {
  margin: 0;
  color: var(--bad);
  font-size: 13px;
}

.wide {
  justify-content: center;
  height: 42px;
  font-size: 14.5px;
}

.foot {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--ink-3);
}

.foot a {
  color: var(--ink);
  text-underline-offset: 2px;
  text-decoration-color: var(--line-strong);
}

.foot a:hover {
  text-decoration-color: currentColor;
}

.done {
  display: grid;
  gap: 14px;
}

.done-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: var(--lime);
  color: var(--on-tile);
}

.done-text {
  margin: 0;
  font-size: 14.5px;
  line-height: 1.5;
}
</style>
