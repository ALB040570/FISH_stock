<template>
  <el-avatar :size="size" :src="src || undefined" class="ua" :class="{ photo: !!src }">{{ src ? '' : initials }}</el-avatar>
</template>
<script setup>
// Аватар пользователя: фото, если загружено, иначе инициалы.
import { computed } from 'vue'
import { avatarSrc, initialsOf } from '../avatar'
const props = defineProps({ user: { type: Object, default: null }, size: { type: Number, default: 28 } })
const src = computed(() => avatarSrc(props.user?.id, props.user?.avatar_ver))
const initials = computed(() => initialsOf(props.user?.name))
</script>
<style scoped>
.ua { background: var(--fs-primary-2); color: var(--fs-on-primary); font-weight: 600; flex: none; }
.ua.photo { background: transparent; }
</style>
