import Vue from "vue";
import VueRouter, { RouteConfig } from "vue-router";
import Table from "@/views/Table.vue";
import Chart from "@/views/Chart.vue";

Vue.use(VueRouter);

const routes: Array<RouteConfig> = [
  {
    path: "/",
    name: "Table",
    component: Table
  },
  {
    path: "/chart",
    name: "Chart",
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () =>
      import(/* webpackChunkName: "about" */ "../views/Chart.vue")
  }
];

const router = new VueRouter({
  mode: "history",
  base: process.env.BASE_URL,
  routes
});

export default router;
