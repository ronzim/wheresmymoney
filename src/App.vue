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
      <div>
        <router-link to="/">Home</router-link> |
        <router-link to="/about">About</router-link>
      </div>
    </v-app-bar>

    <!-- Sizes your content based upon application components -->
    <v-main>
      <!-- Provides the application the proper gutter -->
      <!-- <router-view></router-view> -->
      <v-container fluid>
        <v-row>
          <v-col cols="6">
            <v-card outlined>
              <v-card-title>
                <span class="mr-2"> Total identified Expenses </span>
                <v-spacer></v-spacer>
                <span class="ml-2">
                  {{ `${-idExp.toFixed(2)} €` }}
                </span>
              </v-card-title>
            </v-card>
          </v-col>
          <v-col cols="6">
            <v-card outlined>
              <v-card-title>
                <span class="mr-4"> Coverage </span>
                <v-spacer></v-spacer>
                <span class="ml-4"
                  >{{ (coverage * 100).toFixed(2) }} %
                </span></v-card-title
              >
            </v-card>
          </v-col>
        </v-row>
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
                <span :class="`${getColor(item.identified)}--text`">{{
                  item.identified
                }}</span>
              </template>
            </v-data-table>
          </v-col>
        </v-row>
      </v-container>
    </v-main>

    <v-footer app>
      <v-btn @click="panel = !panel" depressed outlined color="secondary">
        <v-icon>{{ `mdi-arrow-${panel ? "left" : "right"}` }}</v-icon>
      </v-btn>
    </v-footer>
  </v-app>
</template>

<script lang="ts">
import Vue from "vue";
import * as XLSX from "xlsx";
// import "@types/lodash";
import * as _ from "lodash";
// import categories from "@/categories";
// import BarChart from "./BarChart.vue";
import { drawChart, parseExcel } from "@/api.charts";

import Settings from "@/components/Settings.vue";

import { Category } from "@/types";

function ExcelDateToJSDate(serialStr: string) {
  let serial = parseInt(serialStr);
  var utc_days = Math.floor(serial - 25569);
  var utc_value = utc_days * 86400;
  var date_info = new Date(utc_value * 1000);

  var fractional_day = serial - Math.floor(serial) + 0.0000001;

  var total_seconds = Math.floor(86400 * fractional_day);

  var seconds = total_seconds % 60;

  total_seconds -= seconds;

  var hours = Math.floor(total_seconds / (60 * 60));
  var minutes = Math.floor(total_seconds / 60) % 60;

  return new Date(
    date_info.getFullYear(),
    date_info.getMonth(),
    date_info.getDate(),
    hours,
    minutes,
    seconds
  );
}

// https://hackernoon.com/creating-stunning-charts-with-vue-js-and-chart-js-28af584adc0a

export default Vue.extend({
  name: "App",
  data: () => ({
    valueCol: "" as string,
    descCol: "" as string,
    idExp: 0 as number,
    coverage: 0 as number,
    file: [] as File[],
    jsonFile: [] as File[],
    jsonData: [] as any[],
    search: "" as string,
    categories: [] as Category[],
    expenses: [] as any[],
    columns: [] as string[],
    panel: true as boolean
  }),
  components: { Settings },
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
  mounted() {
    // dev
    // console.log("DEV file");
    // fetch("conto2021.xlsx").then(res => {
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
        this.jsonData = jsonData;
        console.log("jsonData", this.jsonData);
        this.columns = jsonData[0]
          ? Object.keys(jsonData[0] as Record<string, unknown>)
          : [];

        setTimeout(() => {
          // it seems that the div is not ready (mounted ?) try with next tick
          console.log(this.categories);
          if (this.categories.length > 0) {
            this.computeAndRender();
          }
        }, 0);
      }
    },
    async loadJson(target: File): Promise<void> {
      const data = await target.arrayBuffer();
      const json = JSON.parse(new TextDecoder().decode(data));
      this.categories = json;
      console.log(this.jsonData);
      if (this.jsonData.length > 0) {
        this.computeAndRender();
      }
    },
    computeAndRender: function () {
      const { expenses, idExp, coverage } = parseExcel(
        this.jsonData,
        this.categories,
        { description: this.descCol, values: this.valueCol }
      );

      this.idExp = idExp;
      this.coverage = coverage;
      this.expenses = expenses;
      setTimeout(() => {
        drawChart(this.expenses, this.getColor);
      }, 0);
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
