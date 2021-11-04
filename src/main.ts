import Vue from "vue";
import App from "./App.vue";
import router from "./router";
import store from "./store";

import Vuetify from "vuetify";
import "vuetify/dist/vuetify.min.css";
import "@mdi/font/css/materialdesignicons.css";

Vue.use(Vuetify);

import colors from "vuetify/lib/util/colors";

const vuetify = new Vuetify({
  theme: {
    dark: true,
    themes: {
      light: {
        primary: colors.green,
        secondary: colors.green.lighten1,
        accent: colors.yellow.darken3,
        error: colors.red.accent3
      },
      dark: {
        primary: colors.blue,
        secondary: colors.blue.darken1,
        accent: colors.yellow.darken3,
        error: colors.red.accent3
      }
    }
  }
});

Vue.config.productionTip = false;

new Vue({
  router,
  store,
  vuetify,
  render: h => h(App)
}).$mount("#app");
