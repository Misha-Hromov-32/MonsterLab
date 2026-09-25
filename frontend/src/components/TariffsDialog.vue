<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, CreditCard, Loader2 } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
import { account, checkout, closeDialog, isPro } from '../lib/account'
import { FEATURE_TITLES } from '../lib/constants'
import { formatDate, priceLabel } from '../lib/format'
import { availableFeatures, features } from '../store'
import type { Plan } from '../lib/types'

const busy = ref(false)
const error = ref('')

const plan = computed(() => account.plan)
const canPay = computed(() => features.value.billing && !!plan.value?.enabled)

const columns = computed(() => {
  const p = plan.value
  if (!p) return []
  return (['free', 'pro'] as Plan[]).map((id) => ({
    id,
    title: id === 'pro' ? 'Pro' : 'Бесплатный',
    price: id === 'pro' ? priceLabel(p.price_rub, p.period_days) : '0 ₽',
    rows: availableFeatures.value.map((f) => ({ f, title: FEATURE_TITLES[f], n: p.limits[id][f] })),
    current: (id === 'pro') === isPro.value && !!account.user,
  }))
})

async function pay() {
  busy.value = true
  error.value = await checkout()
  busy.value = false
}
</script>

<template>
  <ModalDialog title="Тарифы" wide @close="closeDialog">
    <p v-if="account.reason" class="reason">{{ account.reason }}</p>

    <div v-if="!plan" class="loading"><Loader2 :size="18" class="spin" /> Загружаем условия…</div>
    <template v-else>
      <div class="cols">
        <section v-for="c in columns" :key="c.id" class="col" :class="c.id">
          <header>
            <span class="name">{{ c.title }}</span>
            <span v-if="c.current" class="cur">ваш тариф</span>
          </header>
          <strong class="price num">{{ c.price }}</strong>
          <ul>
            <li v-for="r in c.rows" :key="r.f">
              <Check :size="14" aria-hidden="true" />
              <span>{{ r.title }}</span>
              <b class="num">{{ r.n }} в день</b>
            </li>
          </ul>
        </section>
      </div>

      <p class="note">
        Разбор обложки, карта внимания, тест полки и примеры — бесплатно и без входа. Лимиты обновляются каждый день.
      </p>

      <p v-if="error" class="err" role="alert">{{ error }}</p>

      <div v-if="canPay" class="pay">
        <button class="btn primary" :disabled="busy" @click="pay">
          <Loader2 v-if="busy" :size="15" class="spin" /><CreditCard v-else :size="15" />
          {{ isPro ? 'Продлить' : 'Оформить' }} Pro — {{ priceLabel(plan.price_rub, plan.period_days) }}
        </button>
        <span v-if="isPro && account.user?.pro_until" class="until num">
          сейчас действует до {{ formatDate(account.user.pro_until) }}
        </span>
        <span v-else class="until">Безопасная оплата через ЮKassa</span>
      </div>
      <p v-else class="note">Оплата подписки скоро появится.</p>
    </template>
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

.loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-3);
}

.cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.col {
  display: grid;
  align-content: start;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--bg);
}

.col.pro {
  border-color: color-mix(in srgb, var(--lime) 70%, var(--line));
  background: var(--lime-soft);
}

.col header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.name {
  font-size: 15px;
  font-weight: 600;
}

.col.pro .name {
  padding: 1px 9px;
  border-radius: 999px;
  background: var(--lime);
  color: var(--on-tile);
}

.cur {
  font-size: 11px;
  color: var(--ink-3);
}

.price {
  font-size: 22px;
  font-weight: 300;
  letter-spacing: -0.03em;
}

ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

li {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: var(--ink-2);
}

li svg {
  color: var(--good);
}

li b {
  font-weight: 600;
  white-space: nowrap;
  color: var(--ink);
}

.note {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--ink-3);
}

.err {
  margin: 0;
  color: var(--bad);
  font-size: 13px;
}

.pay {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 14px;
}

.pay .btn {
  height: 40px;
  white-space: normal;
}

.until {
  font-size: 11.5px;
  color: var(--ink-3);
}

@media (max-width: 480px) {
  .cols {
    grid-template-columns: 1fr;
  }
  .pay .btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
