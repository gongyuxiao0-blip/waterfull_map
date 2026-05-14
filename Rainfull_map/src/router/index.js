import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: ()=>import('../views/Home.vue') // 你的懒加载写法完全兼容Vite，无需改
  }
]

const router = createRouter({
  // 核心修改：process.env.BASE_URL → import.meta.env.BASE_URL
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router