<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, CreditCard, Loader2 } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
import { account, checkout, closeDialog, isPaid } from '../lib/account'
import { formatDate, plural, quotaLabel } from '../lib/format'
import { availableFeatures, features } from '../store'
import type { Feature, FeatureLimits, PlanInfo } from '../lib/types'

const busy = ref('')
const error = ref('')

const billing = computed(() => account.billing)
const canPay = computed(() => features.value.billing && !!billing.value?.enabled)
const current = computed(() => (isPaid.value ? account.user?.plan : ''))

// сначала то, за что платят (нейросети), потом «технические» функции
const ORDER: Feature[] = ['expert', 'improve', 'choice', 'analyze', 'shelf', 'competitors']

/** Только функции, которые есть на сервере, и только ненулевые квоты. */
const rows = (limits: FeatureLimits) =>
  ORDER.filter((f) => availableFeatures.value.includes(f) && (limits[f] ?? 0) > 0).map((f) => quotaLabel(f, limits[f]))

const demoRows = computed(() => (billing.value ? rows(billing.value.demo) : []))
const days = (p: PlanInfo) => `${p.period_days} ${plural(p.period_days, ['день', 'дня', 'дней'])}`

async function pay(p: PlanInfo) {
  busy.value = p.id
  error.value = await checkout(p.id)
  busy.value = ''
}
</script>

<template>
  <ModalDialog title="Тарифы" wide @close="closeDialog">
    <p v-if="account.reason" class="reason">{{ account.reason }}</p>

    <div v-if="!billing" class="loading"><Loader2 :size="18" class="spin" /> Загружаем условия…</div>
    <template v-else>
      <section class="demo">
        <span class="label">Демо-доступ · после подтверждения почты</span>
        <p>{{ demoRows.join(' · ') }}</p>
      </section>

      <div class="cols">
        <section
          v-for="p in billing.plans"
          :key="p.id"
          class="col"
          :class="{ featured: p.featured, current: current === p.id }"
        >
          <header>
            <span class="name">{{ p.title }}</span>
            <span v-if="current === p.id" class="tag cur">ваш тариф</span>
            <span v-else-if="p.featured" class="tag hot">популярный</span>
          </header>
          <p v-if="p.note" class="pnote">{{ p.note }}</p>
          <div class="price">
            <strong class="num">{{ p.price_rub.toLocaleString('ru-RU') }} ₽</strong>
            <span>/ {{ days(p) }}</span>
          </div>
          <ul>
            <li v-for="r in rows(p.limits)" :key="r"><Check :size="14" aria-hidden="true" />{{ r }}</li>
          </ul>
          <button
            v-if="canPay"
            class="btn wide"
            :class="p.featured ? 'primary' : 'pill'"
            :disabled="!!busy"
            @click="pay(p)"
          >
            <Loader2 v-if="busy === p.id" :size="15" class="spin" /><CreditCard v-else :size="15" />
            {{ current === p.id ? 'Продлить' : 'Выбрать' }}
          </button>
        </section>
      </div>

      <p v-if="error" class="err" role="alert">{{ error }}</p>

      <p class="note">
        <template v-if="isPaid && account.user?.pro_until">
          Сейчас действует «{{ account.user.plan_title }}» до {{ formatDate(account.user.pro_until) }}.
        </template>
        Лимиты действуют в оплаченный период и не переносятся. При продлении срок суммируется.
        <template v-if="canPay">Оплата через ЮKassa: картой, SberPay или ЮMoney.</template>
        <template v-else>Оплата пока недоступна.</template>
        {{ ' ' }}<a href="/legal#terms" target="_blank" rel="noopener">Условия и возврат</a>
      </p>
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

.demo {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: var(--panel-2);
}

.demo p {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}

.cols {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}

.col {
  display: grid;
  grid-template-rows: auto auto auto 1fr auto;
  gap: 10px;
  padding: 16px 14px 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--bg);
}

.col.featured {
  border-color: color-mix(in srgb, var(--lime) 60%, var(--line-strong));
  background: var(--lime-soft);
}

.col.current {
  border-color: var(--ink);
}

.col header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.name {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.tag {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 500;
  white-space: nowrap;
}

.tag.hot {
  background: var(--lime);
  color: var(--on-tile);
}

.tag.cur {
  background: var(--ink);
  color: var(--bg);
}

.pnote {
  margin: -4px 0 0;
  font-size: 12px;
  color: var(--ink-3);
}

.price {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
}

.price strong {
  font-size: 26px;
  font-weight: 300;
  letter-spacing: -0.04em;
}

.price span {
  font-size: 12px;
  color: var(--ink-3);
}

ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  align-content: start;
  gap: 7px;
}

li {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 7px;
  font-size: 12.5px;
  line-height: 1.35;
  color: var(--ink-2);
}

li svg {
  margin-top: 1px;
  color: var(--good);
}

.wide {
  justify-content: center;
  height: 38px;
}

.note {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--ink-3);
}

.note a {
  color: var(--ink-2);
  text-underline-offset: 2px;
}

.err {
  margin: 0;
  color: var(--bad);
  font-size: 13px;
}
</style>
