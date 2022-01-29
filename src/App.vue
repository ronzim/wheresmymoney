<template>
  <v-app>
    <v-navigation-drawer app v-model="panel" clipped mobile-breakpoint="xs">
      <div style="border: 1px solid grey; border-radius: 6px" class="ma-2">
        <v-card rounded outlined color="#363636">
          <v-card-title>Source data</v-card-title>

          <v-file-input
            class="mx-2 mt-2"
            accept=".xls, .xlsx, application/vnd.ms-excel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            label="Load source file"
            prepend-icon="mdi-microsoft-excel"
            outlined
            dense
            dark
            color="secondary"
            height="40px"
            @change="loadFile"
            :value="file"
          >
            <template v-slot:selection="{ text }">
              <v-chip small label color="secondary">
                {{ text }}
              </v-chip>
            </template>
          </v-file-input>

          <v-select
            v-model="descCol"
            dense
            class="mx-2"
            :items="columns"
            label="Descr. column"
            prepend-icon="mdi-text"
            outlined
          ></v-select>
          <v-select
            v-model="valueCol"
            dense
            class="mx-2"
            :items="columns"
            label="Value column"
            prepend-icon="mdi-cash-multiple"
            outlined
          ></v-select>
          <v-switch
            v-model="filterPositiveData"
            :label="`Only expenses ${filterPositiveData.toString()}`"
          ></v-switch>
        </v-card>
      </div>

      <div
        v-if="jsonData.length > 0"
        style="border: 1px solid grey; border-radius: 6px"
        class="ma-2"
      >
        <v-card rounded outlined color="#363636">
          <v-card-title>Categories</v-card-title>
          <v-file-input
            class="mx-2"
            accept=".json"
            label="Load categories"
            prepend-icon="mdi-code-json"
            outlined
            dense
            dark
            color="secondary"
            height="40px"
            @change="loadJson"
            :value="jsonFile"
          >
            <template v-slot:selection="{ text }">
              <v-chip small label color="secondary">
                {{ text }}
              </v-chip>
            </template>
          </v-file-input>

          <div>OR</div>

          <settings />
        </v-card>
      </div>
    </v-navigation-drawer>

    <v-app-bar app clipped-left>
      <v-btn @click="panel = !panel" depressed>
        <v-icon>{{ `mdi-arrow-${panel ? "left" : "right"}` }}</v-icon>
      </v-btn>

      <v-spacer></v-spacer>
      <v-alert
        class="ma-4"
        dense
        :type="message.type"
        border="left"
        elevation="0"
        text
      >
        {{ message.content }}
      </v-alert>
      <v-spacer></v-spacer>
      <v-btn-toggle v-model="view" mandatory>
        <v-btn to="/">
          <v-icon class="mr-2">mdi-table</v-icon>
          Table
        </v-btn>
        <v-btn to="/chart">
          <v-icon class="mr-2">mdi-poll</v-icon>
          Chart
        </v-btn>
        <!-- <v-btn>
          <v-icon>mdi-format-align-right</v-icon>
        </v-btn>
        <v-btn>
          <v-icon>mdi-format-align-justify</v-icon>
        </v-btn> -->
      </v-btn-toggle>
    </v-app-bar>

    <!-- Sizes your content based upon application components -->
    <v-main>
      <!-- Provides the application the proper gutter -->
      <router-view
        :jsonData="jsonData"
        :expenses="expenses"
        :categories="categories"
        :getColorFn="getColor"
      ></router-view>
      <!-- <Table
        :jsonData="jsonData"
        :categories="categories"
        :getColorFn="getColor"
      /> -->
    </v-main>

    <v-footer app>
      <v-spacer></v-spacer>
      <v-card outlined>
        <v-card-title class="pa-2">
          <span class="mr-2"> Total identified Expenses </span>
          <v-spacer></v-spacer>
          <span class="ml-2">
            {{ `${-idExp.toFixed(2)} €` }}
          </span>
        </v-card-title>
      </v-card>
      <v-card outlined class="ml-4">
        <v-card-title class="pa-2">
          <span class="mr-4"> Coverage </span>
          <v-spacer></v-spacer>
          <span class="ml-4"
            >{{ (coverage * 100).toFixed(2) }} %
          </span></v-card-title
        >
      </v-card>
    </v-footer>
  </v-app>
</template>

<script lang="ts">
import Vue from "vue";
import { mapState } from "vuex";
import * as XLSX from "xlsx";
// import "@types/lodash";
import * as _ from "lodash";
// import categories from "@/categories";
// import BarChart from "./BarChart.vue";
import {
  drawChart,
  drawLineChart,
  prepareBarData,
  prepareLineData
} from "@/api.charts";

// import Table from "@/views/Table.vue";
import Settings from "@/components/Settings.vue";

import { Category, Message } from "@/types";

// https://hackernoon.com/creating-stunning-charts-with-vue-js-and-chart-js-28af584adc0a

export default Vue.extend({
  name: "App",
  data: () => ({
    filterPositiveData: true as boolean,
    valueCol: "" as string,
    descCol: "" as string,
    idExp: 0 as number,
    coverage: 0 as number,
    file: [] as File[],
    jsonFile: [] as File[],
    expenses: [] as any[],
    columns: [] as string[],
    panel: true as boolean,
    view: 0
  }),
  components: { Settings },
  computed: {
    ...mapState(["message"]),
    jsonData: {
      get() {
        return this.$store.state.jsonData as any[];
      },
      set(value) {
        this.$store.commit("storeJsonData", value);
      }
    },
    categories: {
      get() {
        return this.$store.state.categories as Category[];
      },
      set(value) {
        this.$store.commit("storeCategories", value);
      }
    }
  },
  mounted() {
    // dev
    // console.warn("DEV file");
    // fetch(
    //   "/mnt/c/Users/Mattia-DVLab/Desktop/conti2021/movimentiConto2021.xls"
    // ).then(res => {
    //   res.arrayBuffer().then(content => {
    //     this.loadFile(new File([content], "ciccio"));
    //   });
    // });
  },
  methods: {
    async loadFile(target: File): Promise<void> {
      if (target) {
        const data = await target.arrayBuffer();
        const workbook = XLSX.read(data, { cellDates: true });
        // convert from workbook to array of arrays
        console.log(workbook.SheetNames);
        const first_worksheet = workbook.Sheets[workbook.SheetNames[0]];
        // const first_worksheet = workbook.Sheets["movimentiConto"];
        const jsonData = XLSX.utils.sheet_to_json(first_worksheet, {
          // header: 1
        });

        // convert dates to string
        jsonData.forEach(data => {
          for (let key in data) {
            if (data[key] instanceof Date) {
              data[key] = data[key].toLocaleDateString();
            }
          }
        });

        this.jsonData = jsonData;
        console.log("jsonData", this.jsonData);
        this.columns = jsonData[0]
          ? Object.keys(jsonData[0] as Record<string, unknown>)
          : [];

        this.message.type = "success";
        this.message.content = "Successfully loaded expense file";

        setTimeout(() => {
          // it seems that the div is not ready (mounted ?) try with next tick
          console.log("cat", this.categories);
          if (this.categories.length > 0) {
            this.computeAndRender();
          } else {
            setTimeout(() => {
              this.message.type = "info";
              this.message.content = "Please load a category file";
            }, 1000);
          }
        }, 0);
      }
    },
    async loadJson(target: File): Promise<void> {
      const data = await target.arrayBuffer();
      const json = JSON.parse(new TextDecoder().decode(data));
      this.categories = json;
      console.log(this.jsonData);
      this.message.type = "success";
      this.message.content = "Successfully loaded category file";
      if (this.jsonData.length > 0) {
        this.computeAndRender();
      }
    },
    computeAndRender: function () {
      const { expenses, idExp, coverage } = prepareLineData(
        this.jsonData,
        this.categories,
        { description: this.descCol, values: this.valueCol },
        this.filterPositiveData
      );

      this.idExp = idExp;
      this.coverage = coverage;
      this.expenses = expenses;

      // change view
      this.$router.push("chart");
    },
    getColor: function (categoryName: string) {
      let categoryObj = this.categories
        .filter(c => c.name == categoryName)
        .pop();
      return categoryObj ? categoryObj.color : "white";
    }
  }
});
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #274eb9;
}
</style>
