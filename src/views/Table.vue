<template>
  <v-container fluid>
    <!-- <v-row>
          <v-col cols="6"> // placeholder </v-col>
          <v-col cols="6"> // placeholder </v-col>
        </v-row> -->
    <v-row>
      <v-col>
        <v-card>
          <v-card-text>
            <div id="chart" v-if="categories.length > 0"></div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    <v-row>
      <v-col>
        <v-data-table
          v-if="this.jsonData.length > 0"
          :headers="headers"
          :items="jsonData"
          dense
          :search="search"
        >
          <template v-slot:item.identified="{ item }">
            <span :class="`${getColorFn(item.identified)}--text`">{{
              item.identified
            }}</span>
          </template>
        </v-data-table>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue, { PropType } from "vue";

import { Category, Message } from "@/types";

export default Vue.extend({
  name: "Table",
  data: () => ({
    search: "" as string
  }),
  props: {
    jsonData: { type: [] as PropType<any[]>, required: true },
    categories: { type: [] as PropType<Category[]>, required: true },
    getColorFn: {
      type: [] as PropType<(arg0: string) => string>,
      required: true
    }
  },
  computed: {
    headers: function () {
      let h = Object.keys(this.jsonData[0]).map(d => ({
        text: d,
        value: d,
        width: "5"
      }));
      h.push({ text: "Categoria", value: "identified", width: "20" });
      return h;
    }
  },
  methods: {}
});
</script>
