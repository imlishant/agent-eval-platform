<template>
  <header class="bar">
    <RouterLink to="/" class="brand">Agent Evals</RouterLink>
    <nav>
      <RouterLink to="/" exact-active-class="active">Runs</RouterLink>
      <RouterLink to="/new" active-class="active">New experiment</RouterLink>
      <RouterLink to="/setup" active-class="active">Models &amp; harnesses</RouterLink>
    </nav>
  </header>
  <RouterView v-slot="{ Component }">
    <Transition name="fade" mode="out-in">
      <component :is="Component" />
    </Transition>
  </RouterView>
</template>

<style scoped>
.bar {
  position: sticky; top: 0; z-index: 10; display: flex; gap: 28px; align-items: baseline;
  padding: 12px 24px; background: color-mix(in srgb, var(--bg) 80%, transparent);
  backdrop-filter: saturate(180%) blur(20px); -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--line);
}
.brand { font-weight: 600; color: var(--text); }
nav { display: flex; gap: 18px; font-size: 14px; }
nav a { color: var(--text-2); }
nav a:hover { color: var(--text); text-decoration: none; }
nav a.active { color: var(--text); font-weight: 500; }
.brand:hover { text-decoration: none; }
</style>
