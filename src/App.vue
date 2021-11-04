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
      <v-container fluid>
        <!-- If using vue-router -->
        <!-- <router-view></router-view> -->
        <bar-chart :chartdata="chartData" :options="chartOptions" />
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
import BarChart from "./BarChart.vue";

// https://hackernoon.com/creating-stunning-charts-with-vue-js-and-chart-js-28af584adc0a

export default Vue.extend({
  name: "App",
  data: () => ({
    file: [] as File[],
    chartData: {} as any,
    chartOptions: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "top"
        },
        title: {
          display: true,
          text: "Chart.js Bar Chart"
        }
      }
    }
  }),
  components: { BarChart },
  methods: {
    async loadFile(target: File): Promise<void> {
      if (target) {
        console.log(target);
        const data = await target.arrayBuffer();
        const workbook = XLSX.read(data);
        /* convert from workbook to array of arrays */
        const first_worksheet = workbook.Sheets[workbook.SheetNames[0]];
        const jsonData = XLSX.utils.sheet_to_json(first_worksheet, {
          // header: 1
        });
        console.log(jsonData);

        const totalExpenses = _.sumBy(jsonData, "Importo");
        console.log(totalExpenses);

        let expenses: any[] = [];

        // Sum for each category
        categories.forEach((category: any) => {
          // filter by tags
          let entries = _.filter(jsonData, function (d: any) {
            // they say a simple for loop would be faster...
            let containsTags = category.tags.some(function (tag: string) {
              return d["Causale / Descrizione"].includes(tag);
            });
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
        console.log("coverage:", (coverage * 100).toFixed(1), "%");

        this.chartData = {
          labels: _.map(expenses, "category"),
          datasets: [
            {
              label: "value",
              data: _.map(expenses, "category"),
              backgroundColor: [
                "rgba(255, 99, 132, 0.2)",
                "rgba(54, 162, 235, 0.2)"
              ],
              borderColor: ["rgba(255, 99, 132, 1)", "rgba(54, 162, 235, 1)"],
              borderWidth: 1
            }
          ]
        };
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
