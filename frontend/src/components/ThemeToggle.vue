<template>
  <!-- Переключатель схемы: светлая / тёмная (theme.js). Подпись — для экранного диктора и подсказки. -->
  <el-tooltip :content="dark ? $t('common.theme_light') : $t('common.theme_dark')" placement="bottom">
    <el-button circle size="small" class="theme-toggle" :aria-label="dark ? $t('common.theme_light') : $t('common.theme_dark')" @click="toggleTheme">
      <el-icon><Sunny v-if="dark" /><Moon v-else /></el-icon>
    </el-button>
  </el-tooltip>
</template>
<script setup>
import { computed } from 'vue'
import { themeMode, toggleTheme } from '../theme'
const dark = computed(() => themeMode.value === 'dark')
</script>
