import * as Plotly from "plotly.js";
import * as _ from "lodash";

import { Category, PlotHTMLElement } from "@/types";

export function prepareLineData(
  jsonData: any,
  categories: Category[],
  columns: { description: string; values: string },
  filterPositiveData: boolean
) {
  let expenses: any[] = [];
  // remove "positive" data
  // if (filterPositiveData) {
  const jsonDataOut = filterPositiveData
    ? jsonData.filter((d: any) => d[columns.values] < 0)
    : jsonData.slice();
  // }
  const totalExpenses = _.sumBy(jsonDataOut, columns.values);

  // Divide each category (this can be shared with prepareBarData)
  categories.forEach((category: any) => {
    // filter by tags
    const entries = _.filter(jsonDataOut, function (d: any) {
      let foundTag = "";
      // they say a simple for loop would be faster...
      const containsTags = category.tags.some(function (tag: string) {
        const hasTag = d[columns.description].includes(tag);
        if (hasTag) {
          foundTag = tag;
        }
        return hasTag;
        // return d[columns.description].includes(tag);
      });

      // store identified
      // console.log(containsTags, d["identified"]);
      if (!d["identified"]) {
        d["identified"] = containsTags ? category.name : undefined;
        // console.log("-->", d["identified"]);
        d["tag"] = foundTag;
      }

      return containsTags;
    });
    // sum filtered values
    const sum = _.sumBy(entries, function (d: any) {
      return -d[columns.values];
    });

    const byDate = _.groupBy(entries, function (d: any) {
      // return d["Data Valuta"].getMonth();
      return d["Data Valuta"].split("/")[1]; // dates have been transformed into strings (NOTE: using local this works only for local = IT ?)
    });

    // sum each group
    const sumByDate = _.mapValues(byDate, (el: [any, ...any[]] | number) => {
      return (el = _.sumBy(el as [any, ...any[]], function (d: any) {
        return -d[columns.values];
      }));
    });

    expenses.push({
      category: category.name,
      value: sum,
      entries,
      byDate: sumByDate
    });
  });

  // expenses.forEach(e => console.log(e));
  // console.log(expenses);

  const coverage = _.sumBy(expenses, "value") / totalExpenses;
  console.log("identified exp", _.sumBy(expenses, "value"));
  console.log("coverage:", (coverage * 100).toFixed(1), "%");

  const idExp = _.sumBy(expenses, "value");

  expenses = _.sortBy(expenses, "value");

  return { expenses, idExp, coverage, jsonDataOut };
}

export function drawChart(expenses: any, getColor: (a: string) => string) {
  // const chartData: Plotly.BarData[] = [
  const chartData: any = [
    {
      x: expenses.map((e: any) => e.category),
      y: expenses.map((e: any) => e.value),
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

export function drawLineChart(expenses: any, getColor: (a: string) => string) {
  console.log(expenses);

  // const chartData: Plotly.BarData[] = [
  const chartData: any = expenses.map((exp: any) => {
    return {
      type: "bar",
      x: Object.keys(exp.byDate),
      y: Object.values(exp.byDate),
      name: exp.category,
      marker: {
        color: getColor(exp.category)
      }
    };
  });

  const layout: Partial<Plotly.Layout> = {
    height: 600,
    title: "Titleee2",
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: {
      family: "Avenir, Helvetica, Arial, sans-serif",
      size: 14,
      color: "#afafaf"
    }
  };

  console.log(chartData);

  Plotly.newPlot("chart", chartData, layout, { responsive: true });

  const graphDiv = <PlotHTMLElement>document.getElementById("chart")!;
  graphDiv.on("plotly_selected", function (eventData: any) {
    console.log(eventData);
  });
}
