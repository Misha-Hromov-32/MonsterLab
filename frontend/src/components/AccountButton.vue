<script setup lang="ts">
import { LogIn, UserRound } from 'lucide-vue-next'
import { account, openAccount, openLogin, signedIn, accountLabel } from '../lib/account'
</script>

<template>
  <button
    v-if="signedIn"
    type="button"
    class="acc"
    :title="accountLabel(account.user)"
    aria-label="Личный кабинет"
    @click="openAccount"
  >
    <UserRound :size="15" aria-hidden="true" />
    <span class="email">Личный кабинет</span>
  </button>
  <button v-else type="button" class="btn pill login" aria-label="Войти" aria-haspopup="dialog" @click="openLogin()">
    <LogIn :size="15" aria-hidden="true" /> <span class="txt">Войти</span>
  </button>
</template>

<style scoped>
.acc {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  max-width: 280px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: var(--panel);
  font-size: 13.5px;
  letter-spacing: -0.02em;
  min-width: 0;
}

.acc:hover {
  border-color: var(--ink-3);
}

.email {
  min-width: 0;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.login {
  height: 38px;
  padding: 0 14px;
  font-size: 14px;
  letter-spacing: -0.02em;
}

@media (max-width: 640px) {
  .email,
  .txt {
    display: none;
  }
  .acc {
    padding: 0 12px;
    min-width: 40px;
  }
}
</style>
