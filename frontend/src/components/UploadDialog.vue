<template>
  <el-dialog :model-value="modelValue" :title="$t('data.upload') + (dtype ? ': ' + tr(dtype, 'title') : '')" width="760px"
             @update:model-value="$emit('update:modelValue', $event)" @closed="reset">
    <el-form label-width="150px">
      <el-form-item :label="$t('data.choose_type')">
        <el-select v-model="type" style="width:100%"><el-option v-for="t in types" :key="t.code" :label="tr(t, 'title')" :value="t.code" /></el-select>
      </el-form-item>
      <el-form-item label="Файл Excel">
        <input ref="fileEl" type="file" accept=".xlsx" @change="onFile" />
        <el-button link type="primary" style="margin-left:8px" @click="tpl">{{ $t('data.template') }}</el-button>
      </el-form-item>
      <el-form-item v-if="dtype?.period_field || dtype?.key_fields?.length" :label="$t('data.mode')">
        <el-radio-group v-model="mode">
          <el-radio value="merge">{{ $t('data.merge') }}</el-radio>
          <el-radio value="replace">{{ $t('data.replace') }}</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item :label="$t('common.comment')"><el-input v-model="comment" /></el-form-item>
    </el-form>
    <div class="muted small">{{ $t('data.missing_hint') }}</div>
    <div v-if="report" style="margin-top:12px">
      <el-alert :type="report.ok ? 'success' : 'error'" :closable="false" show-icon
                :title="report.ok ? $t('data.report_ok') + (report.version ? ` — v${report.version}` : '') : `${$t('data.report_err')}: ${report.errors_total}`">
        <div v-if="report.summary" class="small">{{ $t('data.rows') }}: {{ report.summary.rows }}<template v-if="report.summary.period_from">, {{ report.summary.period_from }}–{{ report.summary.period_to }}</template></div>
      </el-alert>
      <el-table v-if="report.errors.length" :data="report.errors" size="small" max-height="300" style="margin-top:8px" border>
        <el-table-column prop="row" :label="$t('data.row')" width="70" />
        <el-table-column prop="column" :label="$t('data.column')" width="170" />
        <el-table-column prop="message" :label="$t('data.message')" />
      </el-table>
      <el-table v-if="report.warnings?.length" :data="report.warnings" size="small" max-height="160" style="margin-top:8px">
        <el-table-column prop="row" :label="$t('data.row')" width="70" />
        <el-table-column prop="message" :label="$t('data.warnings')" />
      </el-table>
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ $t('common.close') }}</el-button>
      <el-button :disabled="!file || !type" :loading="busy" @click="send(true)">{{ $t('data.dry_run') }}</el-button>
      <el-button type="primary" :disabled="!file || !type" :loading="busy" @click="send(false)">{{ $t('common.upload') }}</el-button>
    </template>
  </el-dialog>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { api, download } from '../api'
import { tr } from '../i18n'
const p = defineProps({ modelValue: Boolean, waterBody: String, types: Array, initialType: String })
const emit = defineEmits(['update:modelValue', 'uploaded'])
const type = ref(p.initialType)
const file = ref(null)
const fileEl = ref(null)
const mode = ref('merge')
const comment = ref('')
const report = ref(null)
const busy = ref(false)
const dtype = computed(() => p.types?.find((t) => t.code === type.value))
watch(() => p.initialType, (v) => { type.value = v })
function onFile(e) { file.value = e.target.files[0]; report.value = null }
function reset() { file.value = null; report.value = null; comment.value = ''; if (fileEl.value) fileEl.value.value = '' }
function tpl() { download('data-admin', `/templates/${type.value}.xlsx`, { water_body: p.waterBody }) }
async function send(dry) {
  busy.value = true
  try {
    report.value = await api.upload('data-admin', '/upload', { water_body: p.waterBody, dataset_type: type.value, file: file.value,
      mode: mode.value, dry_run: dry ? 'true' : 'false', comment: comment.value })
    if (report.value.ok && !dry) emit('uploaded', report.value)
  } catch (e) { report.value = { ok: false, errors: [{ message: e.message }], errors_total: 1 } } finally { busy.value = false }
}
</script>
