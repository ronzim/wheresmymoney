<template>
  <v-row>
    <v-col>
      <v-card>
        <v-card-text>
          <div id="chart"></div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script lang="ts">
import Vue, { PropType } from "vue";

import { Category, Message } from "../types";

import { drawLineChart } from "../api.charts";

export default Vue.extend({
  name: "Table",
  data: () => ({
    search: "" as string
  }),
  props: {
    jsonData: { type: [] as PropType<any[]>, required: true },
    expenses: { type: [] as PropType<any[]>, required: true },
    categories: { type: [] as PropType<Category[]>, required: true },
    getColorFn: {
      type: [] as PropType<(arg0: string) => string>,
      required: true
    }
  },
  mounted: function () {
    drawLineChart(this.expenses, this.getColorFn);
  },
  computed: {},
  methods: {}
});
</script>
