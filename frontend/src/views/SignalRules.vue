<template>
  <div class="page">
    <div class="page-head">
      <div>
        <el-button text @click="$router.push('/design/dashboards')"><el-icon><ArrowLeft /></el-icon>&nbsp;{{ $t('dash.design_title') }}</el-button>
        <h1>{{ $t('wv.rules') }}</h1>
        <div class="sub">{{ $t('wv.rules_sub') }}</div>
      </div>
      <div class="row">
        <el-button v-if="data?.can_edit" type="primary" :loading="busy" @click="save">{{ $t('common.save') }}</el-button>
      </div>
    </div>
    <StateBlock :loading="loading" :error="error">
      <template v-if="data">
        <div v-if="data.updated_at" class="muted small" style="margin-bottom:8px">{{ $t('wv.updated') }}: {{ new Date(data.updated_at).toLocaleString('ru-RU') }} · {{ data.updated_by }}</div>
        <StateBlock :error="saveErr" />
        <div class="rules">
          <div v-for="r in data.rules" :key="r.code" class="card rule" :class="{ off: !r.enabled }">
            <div class="row" style="justify-content:space-between; align-items:flex-start">
              <div>
                <b>{{ tr(r, 'title') }}</b>
                <div class="muted small">{{ r.description }}</div>
              </div>
              <el-switch v-model="r.enabled" :disabled="!data.can_edit" :title="$t('wv.enabled')" />
            </div>
            <div v-for="(spec, k) in r.params" :key="k" class="param">
              <span class="small">{{ spec.title }}</span>
              <el-input-number v-model="r.values[k]" :min="spec.min" :max="spec.max" size="small" :disabled="!data.can_edit || !r.enabled" controls-position="right" style="width:130px" />
              <span class="muted small">{{ $t('wv.default') }}: {{ spec.default }}</span>
            </div>
          </div>
        </div>
      </template>
    </StateBlock>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { tr } from '../i18n'
import StateBlock from '../components/StateBlock.vue'
const { t } = useI18n()
const data = ref(null)
const loading = ref(true)
const error = ref(null)
const saveErr = ref(null)
const busy = ref(false)
async function load() {
  try { data.value = await api.get('dashboards', '/signal-rules') } catch (e) { error.value = e } finally { loading.value = false }
}
async function save() {
  busy.value = true; saveErr.value = null
  try {
    data.value = await api.put('dashboards', '/signal-rules', { rules: data.value.rules.map((r) => ({ code: r.code, enabled: r.enabled, values: r.values })) })
    ElMessage.success(t('wv.rules_saved'))
  } catch (e) { saveErr.value = e } finally { busy.value = false }
}
onMounted(load)
</script>
<style scoped>
.rules { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 12px; }
.rule.off { opacity: 0.6; }
.param { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.param > span:first-child { flex: 1; }
</style>
