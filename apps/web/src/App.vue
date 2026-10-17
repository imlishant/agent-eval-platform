<template>
  <header class="bar">
    <RouterLink to="/" class="brand">Agent Evals</RouterLink>
    <span class="muted small">did the agent get better, and how sure are we?</span>
  </header>
  <RouterView v-slot="{ Component }">
    <Transition name="fade" mode="out-in">
      <component :is="Component" />
    </Transition>
  </RouterView>
</template>

<style scoped>
.bar {
  position: sticky; top: 0; z-index: 10; display: flex; gap: 14px; align-items: baseline;
  padding: 12px 24px; background: color-mix(in srgb, var(--bg) 80%, transparent);
  backdrop-filter: saturate(180%) blur(20px); -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--line);
}
.brand { font-weight: 600; color: var(--text); }
.brand:hover { text-decoration: none; }
</style>
