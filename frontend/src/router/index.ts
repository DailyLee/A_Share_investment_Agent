import { createRouter, createWebHistory } from 'vue-router'
import Analysis from '../views/Analysis.vue'
import History from '../views/History.vue'
import Settings from '../views/Settings.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Analysis',
      component: Analysis,
    },
    {
      path: '/history',
      name: 'History',
      component: History,
    },
    {
      path: '/settings',
      name: 'Settings',
      component: Settings,
    },
  ],
})

export default router
