<template>
  <v-app>
    <v-navigation-drawer app>
      <!-- -->
    </v-navigation-drawer>

    <v-app-bar app>
      <!-- -->
      <div>
        <router-link to="/">Home</router-link> |
        <router-link to="/about">About</router-link>
      </div>
      <v-spacer></v-spacer>
      <v-file-input
        class="mt-6"
        accept=".xls, .xlsx, application/vnd.ms-excel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        label="File input"
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
          <v-chip small label color="primary">
            {{ text }}
          </v-chip>
        </template></v-file-input
      >
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
                Total dentified Expenses
                {{ -idExp }}
                €
              </v-card-title>
            </v-card>
          </v-col>
          <v-col cols="6">
            <v-card outlined>
              <v-card-title>
                Coverage {{ (coverage * 100).toFixed(2) }} %</v-card-title
              >
            </v-card>
          </v-col>
        </v-row>
        <v-row>
          <v-col>
            <v-card>
              <v-card-text>
                <!-- <div id="test" style="height: 100%"></div> -->
                <div id="chart"></div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
        <v-row>
          <v-col>
            <v-data-table
              :headers="headers"
              :items="jsonData"
              dense
              :search="search"
            >
            </v-data-table>
          </v-col>
        </v-row>
      </v-container>
    </v-main>

    <v-footer app>
      <!-- -->
    </v-footer>
  </v-app>
</template>

<script lang="ts">
import Vue from "vue";
import * as XLSX from "xlsx";
// import "@types/lodash";
import * as _ from "lodash";
import categories from "./categories";
// import BarChart from "./BarChart.vue";
import * as Plotly from "plotly.js";

// https://hackernoon.com/creating-stunning-charts-with-vue-js-and-chart-js-28af584adc0a

export default Vue.extend({
  name: "App",
  data: () => ({
    idExp: 0 as number,
    coverage: 0 as number,
    file: [] as File[],
    jsonData: [] as any[],
    search: "" as string
  }),
  components: {},
  computed: {
    headers: function () {
      let h = Object.keys(this.jsonData[0])
        .slice(2, -5)
        .map(d => ({
          text: d,
          value: d
        }));
      h.push({ text: "identified", value: "identified" });
      return h;
    }
  },
  mounted() {
    // dev
    console.log("mounted");
    fetch("conto2021.xlsx").then(res => {
      console.log(res);
      res.arrayBuffer().then(content => {
        console.log("1", content);
        this.loadFile(new File([content], "ciccio"));
      });
    });
  },
  methods: {
    async loadFile(target: File): Promise<void> {
      if (target) {
        console.log(target);
        const data = await target.arrayBuffer();
        console.log("2", data);
        const workbook = XLSX.read(data);
        /* convert from workbook to array of arrays */
        console.log(workbook.SheetNames);
        // const first_worksheet = workbook.Sheets[workbook.SheetNames[0]];
        const first_worksheet = workbook.Sheets["movimentiConto"];
        const jsonData = XLSX.utils.sheet_to_json(first_worksheet, {
          // header: 1
        });
        console.log(jsonData);

        const totalExpenses = _.sumBy(jsonData, "Importo");
        console.log("total exp", totalExpenses);

        let expenses: any[] = [];

        // Sum for each category
        categories.forEach((category: any) => {
          // filter by tags
          let entries = _.filter(jsonData, function (d: any) {
            // they say a simple for loop would be faster...
            let containsTags = category.tags.some(function (tag: string) {
              return d["Causale / Descrizione"].includes(tag);
            });

            // store identified
            if (!d["identified"]) {
              d["identified"] = containsTags ? category.name : undefined;
            }

            return containsTags;
          });
          // sum filtered values
          let sum = _.sumBy(entries, function (d: any) {
            return d["Importo"];
          });
          expenses.push({ category: category.name, value: sum });
        });

        console.log(expenses);

        const coverage = _.sumBy(expenses, "value") / totalExpenses;
        console.log("identified exp", _.sumBy(expenses, "value"));
        console.log("coverage:", (coverage * 100).toFixed(1), "%");

        this.jsonData = jsonData;
        console.log("jsonData", this.jsonData);

        this.idExp = _.sumBy(expenses, "value");
        this.coverage = coverage;

        let chartData: Plotly.BarData[] = [
          {
            x: expenses.map(e => e.category),
            y: expenses.map(e => -e.value),
            type: "bar",
            marker: {
              color: "rgb(158,202,225)",
              opacity: 0.6,
              line: {
                color: "rgb(255,255,255)",
                width: 2
              }
            }
          }
        ];

        const layout: Partial<Plotly.Layout> = {
          title: "Titleee",
          barmode: "stack",
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)"
        };

        setTimeout(() => {
          // it seems that the div is not ready (mounted ?) try with next tick
          Plotly.newPlot("chart", chartData, layout, { responsive: true });
        }, 0);
      }
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
  color: #2c3e50;
}
</style>
