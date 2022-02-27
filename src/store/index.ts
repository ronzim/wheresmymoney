import Vue from "vue";
import Vuex from "vuex";

import { Category, Message } from "@/types";

Vue.use(Vuex);

export default new Vuex.Store({
  state: {
    jsonData: [] as any[],
    categories: [] as Category[],
    message: { type: "info", content: "Please load an expense file" } as Message
  },
  mutations: {
    storeJsonData(state, value) {
      state.jsonData = value;
    },
    storeCategories(state, value) {
      state.categories = value;
    },
    updateDataTag(state, [index, value]) {
      Vue.set(state.jsonData, index, value);
    }
  },
  actions: {},
  modules: {}
});
