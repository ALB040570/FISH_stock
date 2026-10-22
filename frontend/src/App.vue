<template>
  <router-view v-if="$route.meta.public" />
  <AppLayout v-else><router-view :key="$route.meta.queryState ? $route.path : $route.fullPath" /></AppLayout>
</template>
<script setup>
import AppLayout from './components/AppLayout.vue'
</script>
