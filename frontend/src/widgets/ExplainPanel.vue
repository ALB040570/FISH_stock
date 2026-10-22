<template>
  <!-- значок слева — вместо заголовка; подпись — во всплывающей подсказке (подзаголовок виджета не повторяем) -->
  <div class="ex">
    <div v-if="explain?.how?.length" class="ex-s">
      <el-tooltip :content="$t('mon.how')" placement="left"><span class="ex-i" :aria-label="$t('mon.how')"><el-icon><Reading /></el-icon></span></el-tooltip>
      <ul class="ex-b"><li v-for="(h, i) in explain.how" :key="i"><Termed :text="h" /></li></ul>
    </div>
    <div v-if="explain?.now?.length" class="ex-s now">
      <el-tooltip :content="$t('mon.now')" placement="left"><span class="ex-i" :aria-label="$t('mon.now')"><el-icon><View /></el-icon></span></el-tooltip>
      <div class="ex-b"><p v-for="(h, i) in explain.now" :key="i"><Termed :text="h" /></p></div>
    </div>
    <div v-if="explain?.next?.length" class="ex-s">
      <el-tooltip :content="$t('mon.check')" placement="left"><span class="ex-i" :aria-label="$t('mon.check')"><el-icon><Guide /></el-icon></span></el-tooltip>
      <div class="ex-b"><div v-for="x in explain.next" :key="x.widget" class="ex-l"><a href="#" @click.prevent="$emit('go', x.widget)">{{ x.label }} →</a></div></div>
    </div>
  </div>
</template>
<script setup>
import { defineComponent, h } from 'vue'
import { ElTooltip } from 'element-plus'
import i18n from '../i18n'
defineProps({ explain: Object })
defineEmits(['go'])

// термины с подсказкой из глоссария (подчёркнуты пунктиром)
const TERMS = {
  ru: [
    [/95 %(?: интервал)?|полоса/i, 'Интервал, в котором с вероятностью 95 % лежит настоящее среднее: среднее ± 1,96 · σ / √n.'],
    [/медиана/i, 'Значение посередине: половина ловов меньше, половина больше. Не зависит от единичных огромных уловов.'],
    [/улов на усилие/i, 'Улов, делённый на количество лова: на 100 м сети за постановку или на 1 га облова неводом.'],
    [/урожайное поколение|сильное поколение/i, 'Многочисленное поколение одного года рождения; в возрастном составе — яркая диагональ снизу-слева вверх-вправо.'],
    [/выброс\w*/i, 'Лов, улов в котором намного больше обычного (за пределами полуторного размаха «ящика»).'],
    [/половозрел\w*/i, 'Рыбы старше возраста половой зрелости m0 (из «Биологических параметров видов»).'],
    [/\bm0\b/, 'Возраст половой зрелости вида.'], [/\bm1\b/, 'Предельный возраст вида.'], [/\bm2\b/, 'До какого возраста вид служит кормом хищникам.'],
  ],
  kk: [
    [/95 %(?: аралық)?|жолақ/i, 'Шынайы орташа 95 % ықтималдықпен жатқан аралық: орташа ± 1,96 · σ / √n.'],
    [/медиана/i, 'Ортадағы мән: аулаулардың жартысы аз, жартысы көп. Жалғыз үлкен ауланымдарға тәуелді емес.'],
    [/күшке шаққандағы ауланым/i, 'Аулау көлеміне бөлінген ауланым: бір қоюға 100 м ауға немесе сүзекімен 1 га-ға.'],
    [/өнімді ұрпақ|күшті ұрпақ/i, 'Бір туу жылының көп санды ұрпағы; жас құрамында — төменгі-сол жақтан жоғары-оңға ашық диагональ.'],
    [/шығарынды\w*/i, 'Ауланымы әдеттегіден әлдеқайда көп аулау.'],
    [/\bm0\b/, 'Түрдің жыныстық жетілу жасы.'], [/\bm1\b/, 'Түрдің шекті жасы.'], [/\bm2\b/, 'Түр қай жасқа дейін жыртқыштарға жем болады.'],
  ],
}
const Termed = defineComponent({
  props: { text: String },
  setup(props) {
    return () => {
      const list = TERMS[i18n.global.locale.value === 'kk' ? 'kk' : 'ru']
      let parts = [props.text || '']
      for (const [rx, tip] of list) {
        const next = []
        for (const part of parts) {
          if (typeof part !== 'string') { next.push(part); continue }
          const m = part.match(rx)
          if (!m) { next.push(part); continue }
          const i = m.index
          next.push(part.slice(0, i), h(ElTooltip, { content: tip, placement: 'top' }, () => h('span', { class: 'term' }, m[0])), part.slice(i + m[0].length))
        }
        parts = next
      }
      return h('span', parts)
    }
  },
})
</script>
<style scoped>
.ex { font-size: 13.5px; line-height: 1.5; }
.ex-s { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 12px; }
.ex-i { flex: none; width: 26px; height: 26px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
  background: var(--fs-hover); color: var(--fs-primary-2); font-size: 15px; cursor: help; margin-top: 1px; }
.ex-b { min-width: 0; flex: 1; color: var(--fs-text); }
ul.ex-b { margin: 0; padding-left: 16px; }
li { margin: 0 0 3px; }
.now .ex-b { background: var(--fs-selected); border-radius: 8px; padding: 8px 10px; }
.now .ex-i { background: var(--fs-selected); }
.now p { margin: 0 0 6px; }
.now p:last-child { margin: 0; }
.ex-l { margin: 3px 0; }
:deep(.term) { border-bottom: 1px dashed var(--fs-muted); cursor: help; }
</style>
