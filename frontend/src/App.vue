<template>
  <router-view v-if="$route.meta.public || $route.meta.bare" />
  <!-- до первого перехода маршрут ещё пустой (matched = []): на странице входа не рисуем оболочку кабинета -->
  <AppLayout v-else-if="$route.matched.length"><router-view :key="$route.meta.queryState ? $route.path : $route.fullPath" /></AppLayout>
</template>
<script setup>
import AppLayout from './components/AppLayout.vue'
</script>
