<template>
  <div class="ex">
    <div v-if="what" class="ex-s">
      <div class="ex-h">{{ $t('mon.what') }}</div>
      <div class="ex-t">{{ what }}</div>
    </div>
    <div v-if="explain?.how?.length" class="ex-s">
      <div class="ex-h">{{ $t('mon.how') }}</div>
      <ul><li v-for="(h, i) in explain.how" :key="i"><Termed :text="h" /></li></ul>
    </div>
    <div v-if="explain?.now?.length" class="ex-s now">
      <div class="ex-h"><el-icon><View /></el-icon>&nbsp;{{ $t('mon.now') }}</div>
      <p v-for="(h, i) in explain.now" :key="i"><Termed :text="h" /></p>
    </div>
    <div v-if="explain?.next?.length" class="ex-s">
      <div class="ex-h">{{ $t('mon.check') }}</div>
      <div v-for="x in explain.next" :key="x.widget" class="ex-l"><a href="#" @click.prevent="$emit('go', x.widget)">{{ x.label }} →</a></div>
    </div>
  </div>
</template>
<script setup>
import { defineComponent, h } from 'vue'
import { ElTooltip } from 'element-plus'
import i18n from '../i18n'
defineProps({ what: String, explain: Object })
defineEmits(['go'])

// термины с подсказкой из глоссария (подчёркнуты пунктиром)
const TERMS = {
  ru: [
    [/95 %(?: интервал)?|полоса/i, 'Интервал, в котором с вероятностью 95 % лежит настоящее среднее: среднее ± 1,96 · σ / √n.'],
    [/медиана/i, 'Значение посередине: половина ловов меньше, половина больше. Не зависит от единичных огромных уловов.'],
    [/улов на усилие/i, 'Улов, делённый на количество лова: на 100 м сети за постановку или на 1 га облова неводом.'],
    [/урожайное поколение|сильное поколение/i, 'Многочисленное поколение одного года рождения; в возрастном составе — яркая диагональ.'],
    [/выброс\w*/i, 'Лов, улов в котором намного больше обычного (за пределами полуторного размаха «ящика»).'],
    [/половозрел\w*/i, 'Рыбы старше возраста половой зрелости m0 (из «Биологических параметров видов»).'],
    [/\bm0\b/, 'Возраст половой зрелости вида.'], [/\bm1\b/, 'Предельный возраст вида.'], [/\bm2\b/, 'До какого возраста вид служит кормом хищникам.'],
  ],
  kk: [
    [/95 %(?: аралық)?|жолақ/i, 'Шынайы орташа 95 % ықтималдықпен жатқан аралық: орташа ± 1,96 · σ / √n.'],
    [/медиана/i, 'Ортадағы мән: аулаулардың жартысы аз, жартысы көп. Жалғыз үлкен ауланымдарға тәуелді емес.'],
    [/күшке шаққандағы ауланым/i, 'Аулау көлеміне бөлінген ауланым: бір қоюға 100 м ауға немесе сүзекімен 1 га-ға.'],
    [/өнімді ұрпақ|күшті ұрпақ/i, 'Бір туу жылының көп санды ұрпағы; жас құрамында — ашық диагональ.'],
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
.ex-s { margin-bottom: 14px; }
.ex-h { font-weight: 600; font-size: 12.5px; text-transform: uppercase; letter-spacing: .02em; color: var(--fs-muted); margin-bottom: 4px;
  display: flex; align-items: center; }
.ex-t { color: var(--fs-text); }
ul { margin: 0; padding-left: 18px; }
li { margin: 3px 0; }
.now { background: var(--fs-selected); border-radius: 8px; padding: 10px 12px; }
.now p { margin: 0 0 6px; }
.now p:last-child { margin: 0; }
.ex-l { margin: 3px 0; }
:deep(.term) { border-bottom: 1px dashed var(--fs-muted); cursor: help; }
</style>
