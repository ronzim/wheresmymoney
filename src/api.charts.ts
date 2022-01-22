import * as Plotly from "plotly.js";
import * as _ from "lodash";

import { Category, PlotHTMLElement } from "@/types";

export function parseExcel(
  jsonData: any,
  categories: Category[],
  columns: { description: string; values: string }
) {
  let expenses: any[] = [];
  // remove "positive" data
  // jsonData = jsonData.filter((d: any) => d[columns.values] < 0);

  const totalExpenses = _.sumBy(jsonData, columns.values);

  // Sum for each category
  categories.forEach((category: any) => {
    // filter by tags
    const entries = _.filter(jsonData, function (d: any) {
      // they say a simple for loop would be faster...
      const containsTags = category.tags.some(function (tag: string) {
        console.log(columns);
        return d[columns.description].includes(tag);
      });

      // store identified
      if (!d["identified"]) {
        d["identified"] = containsTags ? category.name : undefined;
      }

      return containsTags;
    });
    // sum filtered values
    const sum = _.sumBy(entries, function (d: any) {
      return d[columns.values];
    });
    expenses.push({ category: category.name, value: sum });
  });

  expenses.forEach(e => console.log(e));
  // console.log(expenses);

  const coverage = _.sumBy(expenses, "value") / totalExpenses;
  console.log("identified exp", _.sumBy(expenses, "value"));
  console.log("coverage:", (coverage * 100).toFixed(1), "%");

  const idExp = _.sumBy(expenses, "value");

  expenses = _.sortBy(expenses, "value");

  return { expenses, idExp, coverage };
}

export function drawChart(expenses: any, getColor: (a: string) => string) {
  // const chartData: Plotly.BarData[] = [
  const chartData: any = [
    {
      x: expenses.map((e: any) => e.category),
      y: expenses.map((e: any) => -e.value),
      type: "bar",
      marker: {
        color: expenses.map((e: any) => getColor(e.category)),
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
    plot_bgcolor: "rgba(0,0,0,0)",
    font: {
      family: "Avenir, Helvetica, Arial, sans-serif",
      size: 14,
      color: "#afafaf"
    }
  };

  Plotly.newPlot("chart", chartData, layout, { responsive: true });

  const graphDiv = <PlotHTMLElement>document.getElementById("chart")!;
  graphDiv.on("plotly_selected", function (eventData: any) {
    console.log(eventData);
  });
}
