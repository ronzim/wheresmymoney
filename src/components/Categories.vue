<template>
  <v-card max-width="300" elevation="24">
    <v-container class="py-1 px-1">
      <v-row dense>
        <v-col
          cols="3"
          v-for="category in categories"
          :key="category.name"
          class="pa-0"
        >
          <v-btn
            class="ma-0 pa-1 select-categories text-caption"
            tile
            block
            max-width="100"
            :color="getColorFn(category.name)"
            @click="close(item, category)"
          >
            <span class="text-truncate" style="max-width: 100px">{{
              category.name
            }}</span>
          </v-btn>
        </v-col>
      </v-row>
    </v-container>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from "vue";

import { Category, Message } from "@/types";
import { mapState } from "vuex";

export default Vue.extend({
  name: "Categories",
  data: () => ({}),
  props: {
    categories: { type: [] as PropType<Category[]>, required: true },
    getColorFn: {
      type: [] as PropType<(arg0: string) => string>,
      required: true
    },
    item: {}
  },
  computed: {
    ...mapState(["jsonData"])
  },
  methods: {
    close(item, cat) {
      const index = this.jsonData.indexOf(item);
      console.log("close", item, cat.name, index);
      item.identified = cat.name;
      this.$store.commit("updateData", [index, item]);
      this.$emit("click");
    }
  }
});
</script>

<style scoped>
.select-categories {
  outline-width: thin !important;
  outline: solid;
  outline-color: rgb(75, 75, 75);
}
</style>
