import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import RunPage from './pages/RunPage.vue';
import ExperimentPage from './pages/ExperimentPage.vue';
import TrialPage from './pages/TrialPage.vue';
import './style.css';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: RunPage },
    { path: '/experiments/:id', component: ExperimentPage, props: (r) => ({ id: Number(r.params.id) }) },
    { path: '/trials/:id', component: TrialPage, props: (r) => ({ id: Number(r.params.id) }) },
  ],
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
});

createApp(App).use(router).mount('#app');
