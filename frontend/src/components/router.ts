import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';
import Dashboard from '@/components/dashboard/Dashboard.vue';
import Signup from '@/components/signup/Signup.vue';
import Login from '@/components/login/Login.vue';


const routes: RouteRecordRaw[] = [
  { path: '/', component: Dashboard},
  { path: '/signup', component: Signup},
  { path: '/login', component: Login},
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
    routes,
});

export default router;

