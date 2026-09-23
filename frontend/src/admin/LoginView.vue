<script setup lang="ts">
import { ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import Logo from '../components/Logo.vue'
import { adminApi, setToken } from './adminApi'

const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  if (!password.value) return
  busy.value = true
  error.value = ''
  try {
    setToken((await adminApi.login(password.value)).token)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login">
    <form class="box rise" @submit.prevent="submit">
      <Logo :size="40" :wordmark="false" />
      <h1>Админ-панель</h1>
      <p>Monster Lab · управление главной, примерами и экспертным разбором</p>
      <label class="field">
        <span class="flabel">Пароль</span>
        <input v-model="password" class="input" type="password" autocomplete="current-password" autofocus />
      </label>
      <p v-if="error" class="err" role="alert">{{ error }}</p>
      <button class="btn primary wide" :disabled="busy || !password">
        <Loader2 v-if="busy" :size="15" class="spin" /> Войти
      </button>
      <a href="/" class="back">← на сайт</a>
    </form>
  </div>
</template>

<style scoped>
@import './panel.css';

.login {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 24px;
  background-image: radial-gradient(color-mix(in srgb, var(--ink) 7%, transparent) 1px, transparent 1px);
  background-size: 20px 20px;
}

.box {
  display: grid;
  gap: 14px;
  width: min(100%, 380px);
  padding: 32px;
  border-radius: 18px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

h1 {
  margin: 6px 0 0;
  font-size: 24px;
  font-weight: 300;
  letter-spacing: -0.03em;
}

p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-3);
}

.input {
  height: 42px;
}

.wide {
  height: 42px;
  justify-content: center;
}

.back {
  justify-self: center;
  font-size: 12.5px;
  color: var(--ink-3);
  text-decoration: none;
}

.back:hover {
  color: var(--ink);
}
</style>
