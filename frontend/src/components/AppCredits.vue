<template>
  <!-- Разработчики системы (замечание заказчика 24.10.2026): мелко внизу всех экранов; названия — из справочника «Организации» -->
  <div class="fs-credits" data-test="credits">{{ $t('app.credits') }}</div>
</template>
<style scoped>
.fs-credits { font-size: 11px; line-height: 1.4; color: var(--fs-faint); text-align: center; padding: 5px 12px; }
</style>
