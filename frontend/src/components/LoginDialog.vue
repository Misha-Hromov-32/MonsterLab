<script setup lang="ts">
import { computed, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
import Segmented from './Segmented.vue'
import { account, closeDialog, signIn, type AuthMode } from '../lib/account'
import { toast } from '../store'

const MIN_PASSWORD = 8

const modes: { id: AuthMode; title: string }[] = [
  { id: 'login', title: 'Вход' },
  { id: 'register', title: 'Регистрация' },
]

const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

const register = computed(() => account.authMode === 'register')
const canSubmit = computed(
  () => !busy.value && email.value.trim().length > 2 && password.value.length >= (register.value ? MIN_PASSWORD : 1),
)

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  const mode = account.authMode
  const who = email.value.trim()
  error.value = await signIn(mode, who, password.value)
  busy.value = false
  if (!error.value) toast(mode === 'register' ? `Аккаунт создан: ${who}` : `Вы вошли как ${who}`)
}
</script>

<template>
  <ModalDialog :title="register ? 'Регистрация' : 'Вход'" @close="closeDialog">
    <p v-if="account.reason" class="reason">{{ account.reason }}</p>
    <div class="modes">
      <Segmented
        v-model="account.authMode"
        :options="modes"
        label="Вход или регистрация"
        @update:model-value="error = ''"
      />
    </div>

    <form class="form" novalidate @submit.prevent="submit">
      <label class="field">
        <span class="flabel">Email</span>
        <input
          v-model="email"
          class="input"
          type="email"
          name="email"
          autocomplete="email"
          inputmode="email"
          required
          data-autofocus
        />
      </label>
      <label class="field">
        <span class="flabel">Пароль</span>
        <input
          v-model="password"
          class="input"
          type="password"
          name="password"
          :autocomplete="register ? 'new-password' : 'current-password'"
          :minlength="register ? MIN_PASSWORD : undefined"
          required
          aria-describedby="pw-hint"
        />
        <span id="pw-hint" class="hint">{{ register ? `Не короче ${MIN_PASSWORD} символов` : '' }}</span>
      </label>

      <p v-if="error" class="err" role="alert">{{ error }}</p>

      <button class="btn primary wide" type="submit" :disabled="!canSubmit">
        <Loader2 v-if="busy" :size="15" class="spin" />
        {{ register ? 'Создать аккаунт' : 'Войти' }}
      </button>
    </form>

    <p class="foot">
      Разбор обложек, тест полки и примеры работают без входа. Аккаунт нужен для экспертного разбора и инструментов с
      дневным лимитом.
    </p>
  </ModalDialog>
</template>

<style scoped>
.reason {
  margin: -6px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--lime-soft);
  font-size: 13px;
  line-height: 1.45;
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

.hint {
  min-height: 1em;
  font-size: 11px;
  color: var(--ink-3);
}

.hint:empty {
  display: none;
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

/* вкладки «Вход / Регистрация» — на всю ширину окна */
.modes :deep(.seg) {
  display: flex;
}

.modes :deep(.seg button) {
  flex: 1;
}
</style>
