<script setup lang="ts">
import { computed } from 'vue'
import { CreditCard, FolderOpen, Loader2, LogOut } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
import UsageList from './UsageList.vue'
import { account, closeDialog, isPaid, logout, openLibrary, openTariffs } from '../lib/account'
import { formatDate } from '../lib/format'
import { toast } from '../store'

const user = computed(() => account.user)

function signOut() {
  logout()
  toast('Вы вышли из аккаунта')
}
</script>

<template>
  <ModalDialog title="Аккаунт" @close="closeDialog">
    <div v-if="!user" class="loading"><Loader2 :size="18" class="spin" /> Загружаем…</div>
    <template v-else>
      <div class="who">
        <span class="email" :title="user.email">{{ user.email }}</span>
        <div class="plan">
          <span class="badge" :class="{ pro: isPaid }">{{ user.plan_title }}</span>
          <span v-if="isPaid && user.pro_until" class="until num">до {{ formatDate(user.pro_until) }}</span>
        </div>
      </div>

      <section>
        <span class="label">{{ isPaid ? 'Использовано за период' : 'Демо-доступ' }}</span>
        <UsageList :usage="user.usage" :limits="user.limits" />
        <p class="note">
          {{
            isPaid ? 'Квоты обновятся при продлении тарифа.' : 'Демо-доступ разовый. Для продолжения выберите тариф.'
          }}
        </p>
      </section>

      <div class="actions">
        <button class="btn cabinet" @click="openLibrary"><FolderOpen :size="15" /> Личный кабинет</button>
        <button class="btn primary" @click="openTariffs()">
          <CreditCard :size="15" /> {{ isPaid ? 'Продлить или сменить тариф' : 'Выбрать тариф' }}
        </button>
        <button class="btn ghost logout" @click="signOut"><LogOut :size="15" /> Выйти</button>
      </div>
    </template>
  </ModalDialog>
</template>

<style scoped>
.loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-3);
}

.who {
  display: grid;
  gap: 8px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}

.email {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 16px;
  font-weight: 500;
}

.plan {
  display: flex;
  align-items: center;
  gap: 10px;
}

.badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 9px;
  border-radius: 999px;
  background: var(--panel-2);
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 500;
}

.badge.pro {
  background: var(--lime);
  color: var(--on-tile);
}

.until {
  font-size: 12.5px;
  color: var(--ink-2);
}

section {
  display: grid;
  gap: 12px;
}

.note {
  margin: 0;
  font-size: 11.5px;
  color: var(--ink-3);
}

.err {
  margin: 0;
  color: var(--bad);
  font-size: 13px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.actions .btn.primary,
.actions .cabinet {
  flex: 1 1 100%;
  justify-content: center;
  height: 40px;
  white-space: normal;
}

.logout {
  margin-left: auto;
}
</style>
