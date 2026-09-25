<script setup lang="ts">
import { LogIn, UserRound } from 'lucide-vue-next'
import { account, isPro, openAccount, openLogin, signedIn } from '../lib/account'
</script>

<template>
  <button
    v-if="signedIn"
    type="button"
    class="acc"
    :title="account.user?.email ?? 'Аккаунт'"
    :aria-label="account.user ? `Аккаунт ${account.user.email}, тариф ${isPro ? 'Pro' : 'бесплатный'}` : 'Аккаунт'"
    aria-haspopup="dialog"
    @click="openAccount"
  >
    <UserRound :size="15" aria-hidden="true" />
    <span class="email">{{ account.user?.email ?? 'Аккаунт' }}</span>
    <span v-if="account.user" class="badge" :class="{ pro: isPro, free: !isPro }">{{
      isPro ? 'Pro' : 'Бесплатный'
    }}</span>
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
  padding: 0 6px 0 12px;
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

.badge {
  flex: none;
  height: 24px;
  display: inline-flex;
  align-items: center;
  padding: 0 9px;
  border-radius: 999px;
  background: var(--panel-2);
  color: var(--ink-2);
  font-size: 11.5px;
  font-weight: 500;
}

.badge.pro {
  background: var(--lime);
  color: var(--on-tile);
}

.login {
  height: 38px;
  padding: 0 14px;
  font-size: 14px;
  letter-spacing: -0.02em;
}

/* на телефоне email и «Бесплатный» не помещаются — остаются иконка и плашка Pro */
@media (max-width: 640px) {
  .email,
  .txt,
  .badge.free {
    display: none;
  }
  .acc {
    padding: 0 10px;
  }
  .acc:has(.badge.pro) {
    padding-right: 6px;
  }
}
</style>
