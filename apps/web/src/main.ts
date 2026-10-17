import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import HomePage from './pages/HomePage.vue';
import NewExperimentPage from './pages/NewExperimentPage.vue';
import SetupPage from './pages/SetupPage.vue';
import ExperimentPage from './pages/ExperimentPage.vue';
import TrialPage from './pages/TrialPage.vue';
import './style.css';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomePage },
    { path: '/new', component: NewExperimentPage },
    { path: '/setup', component: SetupPage },
    { path: '/experiments/:id', component: ExperimentPage, props: (r) => ({ id: Number(r.params.id) }) },
    { path: '/trials/:id', component: TrialPage, props: (r) => ({ id: Number(r.params.id) }) },
  ],
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
});

createApp(App).use(router).mount('#app');
