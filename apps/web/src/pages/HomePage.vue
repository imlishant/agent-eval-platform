<template>
  <main class="page stack">
    <div class="row">
      <div>
        <h1>Runs</h1>
        <p class="muted" style="margin: 0">Each run compares two agents on the same tasks, several times each.</p>
      </div>
      <span class="spacer" />
      <RouterLink to="/new"><button class="primary">New experiment</button></RouterLink>
    </div>

    <p v-if="error" class="error">Could not reach the API: {{ error }}</p>
    <section class="card">
      <p v-if="!experiments && !error" class="muted">Loading…</p>
      <div v-if="experiments && !experiments.length" class="empty">
        <p>No experiments yet.</p>
        <RouterLink to="/new">Build your first comparison ›</RouterLink>
      </div>
      <table v-if="experiments?.length">
        <thead><tr><th>#</th><th>Name</th><th>A → B</th><th class="num">N</th><th style="width: 180px">Progress</th><th>Result</th></tr></thead>
        <tbody>
          <tr v-for="e in experiments" :key="e.id" class="link" @click="$router.push(`/experiments/${e.id}`)">
            <td class="muted">{{ e.id }}</td>
            <td><RouterLink :to="`/experiments/${e.id}`">{{ e.name }}</RouterLink></td>
            <td class="small muted">{{ e.config_a_name }} → {{ e.config_b_name }}</td>
            <td class="num">{{ e.n_trials }}</td>
            <td><ProgressBar :p="e.progress" /></td>
            <td><span class="pill" :class="{ good: e.status === 'done' }">{{ e.status === 'done' ? 'finished' : 'running' }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { api } from '../api';
import ProgressBar from '../components/ProgressBar.vue';

const experiments = ref<any[]>();
const error = ref('');
async function load() {
  try {
    experiments.value = await api.experiments();
    error.value = '';
  } catch (e: any) {
    error.value = e.message;
  }
}
let timer: number | undefined;
onMounted(() => {
  load();
  timer = window.setInterval(load, 3000);
});
onUnmounted(() => clearInterval(timer));
</script>

<style scoped>
.empty { text-align: center; padding: 24px 0; }
tr.link { cursor: pointer; transition: background var(--beat) var(--ease); }
tr.link:hover { background: var(--surface-2); }
</style>
