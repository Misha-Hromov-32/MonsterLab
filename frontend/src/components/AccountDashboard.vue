<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  LayoutDashboard,
  Images,
  Gift,
  ClipboardCheck,
  Boxes,
  Handshake,
  Sparkles,
  Zap,
  LogOut,
  Ticket,
  Menu,
} from 'lucide-vue-next'
import BrandMark from './BrandMark.vue'
import CoverLibrary from './CoverLibrary.vue'
import RewardPanel from './RewardPanel.vue'
import RulesView from '../studio/RulesView.vue'
import WbView from '../studio/WbView.vue'
import PartnerView from '../studio/PartnerView.vue'
import {
  account,
  accountLabel,
  isPaid,
  logout,
  openLogin,
  openTariffs,
  redeemPromo,
  refreshMe,
  signedIn,
} from '../lib/account'
import { session } from '../lib/session'
import { cabinetTab, navigateCabinet, type CabinetTab } from '../lib/cabinet'
import { formatDate } from '../lib/format'
import { state, toast } from '../store'
const tabs = [
  { id: 'overview', label: 'Обзор', icon: LayoutDashboard },
  { id: 'covers', label: 'Мои обложки', icon: Images },
  { id: 'rewards', label: 'Бонусы', icon: Gift },
  { id: 'rules', label: 'Правила площадок', icon: ClipboardCheck },
  { id: 'wb', label: 'Аудит каталога WB', icon: Boxes },
  { id: 'partner', label: 'Партнёрская программа', icon: Handshake },
] as const
const tab = computed(() => tabs.find((t) => t.id === cabinetTab.value) ?? tabs[0])
const user = computed(() => account.user),
  promo = ref(''),
  busy = ref(false),
  error = ref(''),
  menu = ref(false),
  fetching = ref(false)
async function reload() {
  fetching.value = true
  try {
    await refreshMe()
  } finally {
    fetching.value = false
  }
}
const returnLabel = computed(() =>
  state.variants.length ? { analyze: 'К разбору', compare: 'К сравнению', shelf: 'К полке' }[state.view] : 'На главную',
)
const previousTitle = document.title
onUnmounted(() => {
  document.title = previousTitle
})
onMounted(() => {
  if (tab.value.id !== 'overview' && !account.user) void reload()
})
watch(
  tab,
  () => {
    menu.value = false
    if (tab.value.id === 'overview' && signedIn.value) void reload()
    document.title = (tab.value.id === 'overview' ? 'Личный кабинет' : tab.value.label) + ' — MonStoreLab'
    document.querySelector('.cab-scroll')?.scrollTo({ top: 0 })
  },
  { immediate: true },
)
async function applyPromo() {
  if (!promo.value.trim() || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const r = await redeemPromo(promo.value)
    if (r.error) error.value = r.error
    else {
      promo.value = ''
      toast(r.message ?? 'Промокод активирован')
    }
  } finally {
    busy.value = false
  }
}
function change(id: CabinetTab) {
  navigateCabinet(id)
}
function leave() {
  logout()
  navigateCabinet(null)
  toast('Вы вышли из аккаунта')
}
</script>
<template>
  <div class="cab-shell">
    <div class="cab-scroll">
      <div class="cab-layout">
        <aside class="cab-side">
          <strong>Личный кабинет</strong
          ><button class="cab-switch" :aria-expanded="menu" @click="menu = !menu"><Menu :size="18" />Разделы</button>
          <nav :class="{ expanded: menu }" aria-label="Разделы личного кабинета">
            <a
              v-for="t in tabs"
              :key="t.id"
              :href="'/account' + (t.id === 'overview' ? '' : '#' + t.id)"
              :aria-current="t.id === tab.id ? 'page' : undefined"
              @click.prevent="change(t.id)"
              ><component :is="t.icon" :size="18" />{{ t.label }}</a
            >
          </nav>
          <a href="/" class="cab-back" @click.prevent="navigateCabinet(null)"
            ><ArrowLeft :size="16" /> {{ returnLabel }}</a
          >
          <button v-if="signedIn" class="cab-exit" @click="leave"><LogOut :size="16" /> Выйти</button>
        </aside>
        <main class="cab-page" :key="session.token">
          <template v-if="!signedIn"
            ><h1>{{ tab.id === 'overview' ? 'Личный кабинет' : tab.label }}</h1>
            <section class="cab-paper">
              <p>Войдите, чтобы открыть свои обложки, баланс и инструменты продавца.</p>
              <button class="lab-primary" @click="openLogin()">
                Войти в кабинет <ArrowRight :size="16" />
              </button></section
          ></template>
          <template v-else-if="!user"
            ><h1>Личный кабинет</h1>
            <p role="status">{{ fetching ? 'Загружаем аккаунт…' : 'Не удалось загрузить аккаунт.' }}</p>
            <button v-if="!fetching" class="lab-secondary" @click="reload">Повторить</button></template
          >
          <template v-else-if="tab.id === 'overview'"
            ><div class="cab-heading">
              <div>
                <h1>Мой кабинет</h1>
                <span class="cab-email ym-hide-content">{{ accountLabel(user) }}</span>
              </div>
              <a href="/#generator" class="lab-primary"><Sparkles :size="18" /> Создать обложку</a>
            </div>
            <div class="cab-cards">
              <section class="cab-balance">
                <BrandMark class="balance-mark" :size="180" />
                <h2><Zap :size="18" /> Баланс импульсов</h2>
                <strong class="balance-number">{{ user.wallet?.remaining?.toLocaleString('ru-RU') ?? '—' }}</strong
                ><a href="/account#rewards" @click.prevent="change('rewards')"
                  >Получить бонусы <ArrowRight :size="15"
                /></a>
              </section>
              <section class="cab-plan">
                <h2>Ваш тариф</h2>
                <strong>{{ isPaid ? user.plan_title : 'Бесплатный' }}</strong>
                <p v-if="isPaid && user.pro_until">Действует до {{ formatDate(user.pro_until) }}</p>
                <p v-else>Доступ в пределах баланса импульсов</p>
                <button @click="openTariffs()">
                  {{ isPaid ? 'Управлять тарифом' : 'Выбрать тариф' }} <ArrowRight :size="15" />
                </button>
              </section>
            </div>
            <p v-for="term in user.upcoming" :key="term.starts">
              Тариф «{{ term.title }}» оплачен с {{ formatDate(term.starts) }} по {{ formatDate(term.ends) }}.
            </p>
            <header class="recent-head">
              <h2 class="cab-subhead">Последние обложки</h2>
              <a href="/account#covers" @click.prevent="change('covers')">Все обложки <ArrowRight :size="15" /></a>
            </header>
            <CoverLibrary recent />
            <details class="cab-promo">
              <summary><Ticket :size="19" /> Активировать промокод</summary>
              <form @submit.prevent="applyPromo">
                <label class="lab-field"
                  >Промокод<input v-model="promo" maxlength="40" autocomplete="off" required /></label
                ><button class="lab-secondary" :disabled="busy || !promo.trim()">Активировать</button>
              </form>
              <p v-if="error" role="alert">{{ error }}</p>
            </details></template
          >
          <template v-else-if="tab.id === 'covers'"
            ><div class="cab-heading">
              <h1>Мои обложки</h1>
              <a href="/#generator" class="lab-primary"><Sparkles :size="17" /> Создать обложку</a>
            </div>
            <CoverLibrary
          /></template>
          <template v-else-if="tab.id === 'rewards'"
            ><h1>Бонусы</h1>
            <RewardPanel
          /></template>
          <div v-else class="studio-tools">
            <RulesView v-if="tab.id === 'rules'" /><WbView v-else-if="tab.id === 'wb'" /><PartnerView v-else />
          </div>
        </main>
      </div>
    </div>
  </div>
</template>
<style scoped>
.recent-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 28px 0 12px;
}
.recent-head .cab-subhead {
  margin: 0;
}
.recent-head a {
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--ink);
  text-decoration: none;
  font-size: 14px;
}
.cab-shell {
  min-height: 0;
  min-width: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr);
  background: var(--cabinet-canvas);
}

.cab-exit,
.cab-switch,
.cab-back {
  display: flex;
  align-items: center;
  gap: 9px;
}
.cab-scroll {
  overflow: auto;
}
.cab-layout {
  display: grid;
  grid-template-columns: 242px minmax(0, 1fr);
  gap: clamp(28px, 4vw, 64px);
  max-width: 1390px;
  margin: auto;
  padding: clamp(28px, 4vw, 62px) clamp(18px, 4vw, 64px) 80px;
  align-items: start;
}
.cab-side {
  position: sticky;
  top: 24px;
  padding: 22px 12px 12px;
  border: 1px solid #432d45;
  background: #2b1e30;
  border-radius: 18px;
  color: #fff;
}
.cab-side > strong {
  display: block;
  margin: 0 0 18px 10px;
  font-size: 16px;
}
.cab-side nav {
  display: grid;
  gap: 4px;
}
.cab-side nav a,
.cab-exit,
.cab-switch {
  border: 0;
  background: transparent;
  padding: 11px 12px;
  border-radius: 10px;
  color: var(--ink-2);
  font-size: 14px;
  font-weight: 550;
  text-decoration: none;
}
.cab-side nav a {
  display: flex;
  align-items: center;
  gap: 10px;
}
.cab-side nav a,
.cab-exit,
.cab-back {
  color: #e7dfe8;
}
.cab-side nav a:hover,
.cab-exit:hover,
.cab-back:hover {
  background: #453348;
  color: white;
}
.cab-side nav a[aria-current] {
  background: #f7def3;
  color: #3a1435;
  font-weight: 700;
}
.cab-side nav a[aria-current] svg {
  color: #8d247d;
}
.cab-back {
  margin-top: 16px;
  border-top: 1px solid #59445a;
  padding: 15px 12px 8px;
  font-size: 14px;
  text-decoration: none;
}
.cab-exit {
  margin-top: 4px;
}
.cab-page {
  color: var(--ink);
}
.cab-side nav a:focus-visible,
.cab-back:focus-visible,
.cab-switch:focus-visible,
.cab-exit:focus-visible {
  outline: 2px solid #f1a8e8;
  outline-offset: 1px;
}
.cab-switch {
  display: none;
}
.cab-page {
  min-width: 0;
}
.cab-page h1,
.studio-tools :deep(h1) {
  font: 850 clamp(32px, 4vw, 56px)/1.07 var(--display-font);
  letter-spacing: -0.065em;
  margin: 0 0 20px;
}
.cab-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.cab-heading h1 {
  margin: 0;
}
.cab-email {
  display: block;
  margin-top: 7px;
  color: var(--ink-2);
  overflow-wrap: anywhere;
}
.cab-cards {
  display: grid;
  grid-template-columns: 1.17fr 1fr;
  gap: 14px;
}
.cab-balance,
.cab-plan,
.cab-paper {
  padding: clamp(20px, 2.4vw, 32px);
  border-radius: 20px;
  position: relative;
  overflow: hidden;
}
.cab-balance {
  background: #291126;
  color: white;
  isolation: isolate;
}
.balance-mark {
  position: absolute;
  right: -25px;
  bottom: -46px;
  transform: rotate(-14deg);
  opacity: 0.25;
  color: #e857c9;
  z-index: -1;
}
.cab-cards h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 550;
}
.cab-balance h2 svg {
  color: #fb78e6;
}
.balance-number {
  font: 850 clamp(48px, 6vw, 80px)/1.12 var(--display-font);
  letter-spacing: -0.07em;
  display: block;
  margin: 10px 0 15px;
}
.cab-balance a,
.cab-plan button {
  display: inline-flex;
  gap: 9px;
  align-items: center;
  color: inherit;
  background: transparent;
  padding: 0;
  border: 0;
  text-decoration: none;
  font-weight: 650;
}
.cab-plan,
.cab-paper {
  background: var(--panel);
  border: 1px solid var(--line);
}
.cab-plan > strong {
  display: block;
  margin: 17px 0 2px;
  font-size: clamp(22px, 2.8vw, 34px);
  letter-spacing: -0.04em;
}
.cab-plan p {
  margin: 0 0 16px;
  color: var(--ink-2);
  font-size: 14px;
}
.cab-subhead {
  margin: 32px 0 14px;
  letter-spacing: -0.04em;
  font-size: 25px;
}
.cab-promo:hover {
  border-color: var(--line-strong);
}
.cab-promo {
  background: var(--panel);
  border: 1px solid var(--line);
  padding: 18px 20px;
  border-radius: 14px;
  margin-top: 18px;
}
.cab-promo summary {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-weight: 600;
}
.cab-promo summary:after {
  content: '+';
  margin-left: auto;
}
.cab-promo[open] summary:after {
  content: '−';
}
.cab-promo form {
  margin-top: 16px;
  display: flex;
  align-items: end;
  flex-wrap: wrap;
  gap: 10px;
}
@media (max-width: 850px) {
  .cab-layout {
    grid-template-columns: 1fr;
    gap: 22px;
    padding-top: 16px;
  }
  .cab-side {
    position: static;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
    padding: 8px 10px;
    border-radius: 12px;
  }
  .cab-side > strong {
    display: none;
  }
  .cab-switch {
    display: flex;
    color: #fff;
    background: #49364d;
    border: 1px solid #6a516b;
    padding: 8px 10px;
    min-height: 38px;
  }
  .cab-back {
    margin: 0 0 0 auto;
    border: 0;
    font-size: 13px;
    padding: 10px 6px;
  }
  .cab-exit {
    margin: 0;
    padding: 10px;
    font-size: 0;
    gap: 0;
  }
  .cab-side nav {
    display: none;
    order: 4;
    width: 100%;
  }
  .cab-side nav.expanded {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 560px) {
  .cab-cards {
    grid-template-columns: 1fr;
  }
  .cab-cards {
    gap: 10px;
  }
  .cab-plan {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 6px;
  }
  .cab-plan > strong {
    grid-column: 1;
    grid-row: 2;
    margin: 0;
  }
  .cab-plan p {
    grid-row: 3;
    grid-column: 1/-1;
    margin: 0;
  }
  .cab-plan button {
    grid-column: 2;
    grid-row: 1/3;
    font-size: 13px;
  }
  .cab-heading {
    align-items: start;
  }
  .cab-subhead {
    font-size: 21px;
    margin-top: 24px;
  }
}
</style>
