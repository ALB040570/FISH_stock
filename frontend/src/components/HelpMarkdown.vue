<template>
  <!-- eslint-disable-next-line vue/no-v-html — HTML в Markdown отключён (html: false), вывод безопасен -->
  <div class="help-md" @click="onClick" v-html="html" />
</template>
<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { useAuth } from '../store/auth'
import { helpPath } from '../cabinets'

const props = defineProps({ source: { type: String, default: '' }, stripTitle: Boolean })
const emit = defineEmits(['navigate'])
const router = useRouter()
const auth = useAuth()

const md = new MarkdownIt({ html: false, linkify: true, breaks: false })
  .use(texmath, { engine: katex, delimiters: 'dollars', katexOptions: { throwOnError: false } })

// рисунки справки: help-image:<имя> (загружены в приложении), bundled:<имя> (поставка)
const defaultImage = md.renderer.rules.image
md.renderer.rules.image = (tokens, idx, options, env, self) => {
  const t = tokens[idx]
  const src = t.attrGet('src') || ''
  const tok = encodeURIComponent(auth.accessToken || '')
  if (src.startsWith('help-image:')) t.attrSet('src', `/api/help/images/${src.slice(11)}?access_token=${tok}`)
  else if (src.startsWith('bundled:')) t.attrSet('src', `/api/help/bundled/${src.slice(8)}?access_token=${tok}`)
  return defaultImage(tokens, idx, options, env, self)
}
// ссылки на статьи справки: [текст](help:<код статьи>)
md.validateLink = (url) => !/^(javascript|vbscript|data):/i.test(url.trim())
const defaultLink = md.renderer.rules.link_open || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const t = tokens[idx]
  const href = t.attrGet('href') || ''
  if (href.startsWith('help:')) { t.attrSet('data-help', href.slice(5)); t.attrSet('href', helpPath(href.slice(5))) }
  else if (/^https?:/.test(href)) { t.attrSet('target', '_blank'); t.attrSet('rel', 'noopener') }
  return defaultLink(tokens, idx, options, env, self)
}

const html = computed(() => {
  let s = props.source || ''
  if (props.stripTitle) s = s.replace(/^# .*\n?/, '')
  return md.render(s)
})

function onClick(e) {
  const a = e.target.closest('a[data-help]')
  if (a) {
    e.preventDefault()
    emit('navigate', a.dataset.help)
    router.push(helpPath(a.dataset.help))
  }
}
</script>
<style>
.help-md { line-height: 1.65; font-size: 15px; color: var(--fs-text); }
.help-md h1 { font-size: 24px; margin: 0 0 14px; }
.help-md h2 { font-size: 19px; margin: 26px 0 10px; padding-bottom: 4px; border-bottom: 1px solid var(--fs-line); }
.help-md h3 { font-size: 16px; margin: 20px 0 8px; }
.help-md p { margin: 0 0 10px; }
.help-md ul, .help-md ol { margin: 0 0 12px; padding-left: 24px; }
.help-md li { margin: 3px 0; }
.help-md code { background: var(--fs-code); border-radius: 4px; padding: 1px 5px; font-size: 13px; }
.help-md pre { background: var(--fs-code); border-radius: 6px; padding: 10px 14px; overflow-x: auto; }
.help-md pre code { background: none; padding: 0; }
.help-md blockquote { margin: 12px 0; padding: 8px 14px; border-left: 4px solid var(--fs-primary-soft); background: var(--fs-selected); color: var(--el-text-color-regular); border-radius: 0; }
.help-md blockquote p:last-child { margin: 0; }
.help-md table { border-collapse: collapse; margin: 10px 0 14px; font-size: 13.5px; display: block; overflow-x: auto; }
.help-md th, .help-md td { border: 1px solid var(--fs-line); padding: 5px 9px; text-align: left; vertical-align: top; }
.help-md th { background: var(--fs-card-soft); font-weight: 600; }
.help-md img { max-width: 100%; border: 1px solid var(--fs-line); border-radius: 4px; }
.help-md eq, .help-md eqn { font-size: 1.02em; }
.help-md section.katex-display, .help-md .katex-display { overflow-x: auto; overflow-y: hidden; padding: 4px 0; }
</style>
