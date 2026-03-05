import { App } from "@modelcontextprotocol/ext-apps";
import {
  applyDocumentTheme,
  applyHostStyleVariables,
  applyHostFonts,
} from "@modelcontextprotocol/ext-apps";
import * as echarts from "echarts";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let chartInstance: any = null;
let currentData: Record<string, unknown>[] = [];
let currentTitle = "Query Results";
let isDark = false;

// ---------------------------------------------------------------------------
// DOM
// ---------------------------------------------------------------------------
const cardEl = document.querySelector(".card") as HTMLElement;
const cardHeaderEl = document.querySelector(".card-header") as HTMLElement;
const cardTitleEl = document.getElementById("card-title") as HTMLElement;
const chartTypeSelect = document.getElementById(
  "chart-type",
) as HTMLSelectElement;
const xColumnSelect = document.getElementById("x-column") as HTMLSelectElement;
const chartEl = document.getElementById("chart")!;

// ---------------------------------------------------------------------------
// MCP App setup — register ALL handlers before connect()
// ---------------------------------------------------------------------------
const app = new App({ name: "Teradata Query Visualizer", version: "1.0.0" });

app.ontoolinput = () => {
  showStatus("Loading chart data...");
};

app.ontoolresult = (result) => {
  try {
    const textItem = result.content?.find(
      (c: { type: string }) => c.type === "text",
    ) as { type: string; text: string } | undefined;

    if (!textItem?.text) {
      showStatus("No data received", true);
      return;
    }

    const raw = textItem.text.trim();

    // Try parsing as structured JSON result
    let parsed: any;
    try {
      parsed = JSON.parse(raw);
    } catch {
      // Not JSON — treat the whole text as an error/info message
      showStatus(raw, true);
      return;
    }

    // Check for error wrapper
    if (parsed.error) {
      showStatus(parsed.error, true);
      return;
    }

    currentData = parsed.data;
    currentTitle = parsed.title || "Query Results";

    if (!currentData?.length) {
      showStatus("No rows in result set");
      return;
    }

    populateColumnSelectors();
    renderChart();
  } catch (e) {
    showStatus(`Unexpected error: ${e}`, true);
  }
};

app.ontoolcancelled = () => {
  showStatus("Query cancelled");
};

app.onerror = (err) => {
  showStatus(`Error: ${err}`, true);
};

app.onhostcontextchanged = (ctx: any) => {
  // Apply host styling
  applyDocumentTheme(ctx);
  applyHostStyleVariables(ctx);
  applyHostFonts(ctx);

  // Handle safe area insets
  if (ctx.safeAreaInsets) {
    const { top, right, bottom, left } = ctx.safeAreaInsets;
    document.body.style.padding = `${top}px ${right}px ${bottom}px ${left}px`;
  }

  // Detect dark mode from host context
  const wasDark = isDark;
  isDark = ctx.theme === "dark";

  if (wasDark !== isDark && chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
    renderChart();
  }
};

app.onteardown = () => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
};

// Connect after all handlers are registered
app.connect();

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------
chartTypeSelect.addEventListener("change", renderChart);
xColumnSelect.addEventListener("change", renderChart);

// Responsive resize
const resizeObserver = new ResizeObserver(() => {
  chartInstance?.resize();
});
resizeObserver.observe(chartEl);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function showStatus(message: string, isError = false) {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
  cardHeaderEl.style.display = "none";

  if (isError) {
    // Collapse the entire app to zero so the host iframe is effectively invisible
    chartEl.innerHTML = "";
    chartEl.style.height = "0";
    cardEl.style.display = "none";
    document.body.style.overflow = "hidden";
    document.body.style.height = "0";
    document.body.style.padding = "0";
  } else {
    cardEl.style.display = "";
    chartEl.style.height = "";
    document.body.style.overflow = "";
    document.body.style.height = "";
    document.body.style.padding = "";
    chartEl.innerHTML = `<div class="status-message">${escapeHtml(message)}</div>`;
  }
}

function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getColumns() {
  if (!currentData.length) return { all: [], strings: [], numbers: [] };
  const row = currentData[0];
  const all = Object.keys(row);
  const strings = all.filter((col) => typeof row[col] === "string");
  const numbers = all.filter((col) => typeof row[col] === "number");
  return { all, strings, numbers };
}

function populateColumnSelectors() {
  const { all, strings } = getColumns();

  xColumnSelect.innerHTML = "";
  const candidates = strings.length > 0 ? strings : all;
  candidates.forEach((col) => {
    const opt = document.createElement("option");
    opt.value = col;
    opt.textContent = col;
    xColumnSelect.appendChild(opt);
  });
}

function getXColumn(): string {
  const { strings, all } = getColumns();
  return xColumnSelect.value || strings[0] || all[0];
}

function getValueColumns(): string[] {
  const xCol = getXColumn();
  const { numbers, all } = getColumns();
  const vals = numbers.filter((c) => c !== xCol);
  return vals.length > 0 ? vals : all.filter((c) => c !== xCol);
}

function getCategories(): string[] {
  const xCol = getXColumn();
  return currentData.map((row) => String(row[xCol]));
}

function getSeriesData(col: string): number[] {
  return currentData.map((row) => {
    const v = row[col];
    return typeof v === "number" ? v : parseFloat(String(v)) || 0;
  });
}

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------
const COLORS = [
  "#5470c6",
  "#91cc75",
  "#fac858",
  "#ee6666",
  "#73c0de",
  "#3ba272",
  "#fc8452",
  "#9a60b4",
  "#ea7ccc",
];

// ---------------------------------------------------------------------------
// Shared option base
// ---------------------------------------------------------------------------
function baseOption() {
  return {
    tooltip: {
      trigger: "axis" as const,
      axisPointer: { type: "shadow" as const },
    },
    legend: {
      bottom: 0,
      textStyle: { color: isDark ? "#a0a0b0" : "#666", fontSize: 12 },
    },
    grid: {
      top: 24,
      right: 24,
      bottom: 40,
      left: 16,
      containLabel: true,
    },
    color: COLORS,
  };
}

function axisLabelStyle() {
  return { color: isDark ? "#a0a0b0" : "#666", fontSize: 11 };
}

function splitLineStyle() {
  return { lineStyle: { color: isDark ? "#2a2a4a" : "#eee" } };
}

// ---------------------------------------------------------------------------
// Chart option builders
// ---------------------------------------------------------------------------

function basicBarOption() {
  const cats = getCategories();
  const cols = getValueColumns();
  return {
    ...baseOption(),
    xAxis: {
      type: "category",
      data: cats,
      axisLabel: {
        ...axisLabelStyle(),
        rotate: cats.length > 10 ? 35 : 0,
      },
    },
    yAxis: {
      type: "value",
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    series: cols.map((col) => ({
      name: col,
      type: "bar",
      data: getSeriesData(col),
    })),
  };
}

function stackedBarOption() {
  const opt = basicBarOption();
  opt.series = opt.series.map((s: any) => ({
    ...s,
    stack: "total",
    emphasis: { focus: "series" },
  }));
  return opt;
}

function horizontalBarOption() {
  const cats = getCategories();
  const cols = getValueColumns();
  return {
    ...baseOption(),
    grid: { ...baseOption().grid, left: 24 },
    yAxis: {
      type: "category",
      data: cats,
      axisLabel: axisLabelStyle(),
    },
    xAxis: {
      type: "value",
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    series: cols.map((col) => ({
      name: col,
      type: "bar",
      data: getSeriesData(col),
    })),
  };
}

function stackedHorizontalOption() {
  const opt = horizontalBarOption();
  opt.series = opt.series.map((s: any) => ({
    ...s,
    stack: "total",
    emphasis: { focus: "series" },
  }));
  return opt;
}

function sortedBarOption() {
  const cats = getCategories();
  const cols = getValueColumns();
  const primaryData = getSeriesData(cols[0]);

  // Sort indices by primary column descending
  const indices = cats.map((_, i) => i);
  indices.sort((a, b) => primaryData[b] - primaryData[a]);

  const sortedCats = indices.map((i) => cats[i]);

  return {
    ...baseOption(),
    xAxis: {
      type: "category",
      data: sortedCats,
      axisLabel: {
        ...axisLabelStyle(),
        rotate: sortedCats.length > 10 ? 35 : 0,
      },
    },
    yAxis: {
      type: "value",
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    series: cols.map((col) => {
      const data = getSeriesData(col);
      return {
        name: col,
        type: "bar",
        data: indices.map((i) => data[i]),
      };
    }),
  };
}

function waterfallOption() {
  const cats = getCategories();
  const cols = getValueColumns();
  const values = getSeriesData(cols[0]);

  // Calculate waterfall cumulative bases
  let cumulative = 0;
  const invisibleData: number[] = [];
  const barData: Array<{ value: number; itemStyle: { color: string } }> = [];

  values.forEach((v) => {
    if (v >= 0) {
      invisibleData.push(cumulative);
      barData.push({ value: v, itemStyle: { color: COLORS[1] } });
    } else {
      invisibleData.push(cumulative + v);
      barData.push({ value: Math.abs(v), itemStyle: { color: COLORS[3] } });
    }
    cumulative += v;
  });

  // Append total
  const allCats = [...cats, "Total"];
  invisibleData.push(0);
  barData.push({
    value: cumulative,
    itemStyle: { color: COLORS[0] },
  });

  return {
    ...baseOption(),
    xAxis: {
      type: "category",
      data: allCats,
      axisLabel: {
        ...axisLabelStyle(),
        rotate: allCats.length > 10 ? 35 : 0,
      },
    },
    yAxis: {
      type: "value",
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    legend: { show: false },
    series: [
      {
        name: "Base",
        type: "bar",
        stack: "waterfall",
        silent: true,
        itemStyle: { borderColor: "transparent", color: "transparent" },
        emphasis: {
          itemStyle: { borderColor: "transparent", color: "transparent" },
        },
        data: invisibleData,
      },
      {
        name: cols[0],
        type: "bar",
        stack: "waterfall",
        label: {
          show: true,
          position: "top",
          color: isDark ? "#ccc" : "#333",
          fontSize: 11,
          formatter: (params: any) => {
            const idx = params.dataIndex;
            if (idx === allCats.length - 1)
              return cumulative >= 0
                ? `+${cumulative}`
                : String(cumulative);
            const v = values[idx];
            return v >= 0 ? `+${v}` : String(v);
          },
        },
        data: barData,
      },
    ],
  };
}

function roundedBarOption() {
  const opt = basicBarOption();
  opt.series = opt.series.map((s: any) => ({
    ...s,
    itemStyle: { borderRadius: [8, 8, 0, 0] },
    barMaxWidth: 40,
  }));
  return opt;
}

function polarBarOption() {
  const cats = getCategories();
  const cols = getValueColumns();
  const values = getSeriesData(cols[0]);
  const maxVal = Math.max(...values) * 1.2;

  return {
    tooltip: {},
    color: COLORS,
    polar: { radius: [30, "70%"] },
    angleAxis: {
      max: maxVal,
      startAngle: 90,
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    radiusAxis: {
      type: "category",
      data: cats,
      axisLabel: axisLabelStyle(),
    },
    series: [
      {
        type: "bar",
        data: values.map((v, i) => ({
          value: v,
          itemStyle: { color: COLORS[i % COLORS.length] },
        })),
        coordinateSystem: "polar",
        label: {
          show: true,
          position: "middle",
          formatter: "{c}",
          color: "#fff",
          fontSize: 11,
        },
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Line chart option builders
// ---------------------------------------------------------------------------

function basicLineOption() {
  const cats = getCategories();
  const cols = getValueColumns();
  return {
    ...baseOption(),
    xAxis: {
      type: "category",
      data: cats,
      boundaryGap: false,
      axisLabel: {
        ...axisLabelStyle(),
        rotate: cats.length > 10 ? 35 : 0,
      },
    },
    yAxis: {
      type: "value",
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    series: cols.map((col) => ({
      name: col,
      type: "line",
      data: getSeriesData(col),
      symbol: "circle",
      symbolSize: 6,
    })),
  };
}

function smoothLineOption() {
  const opt = basicLineOption();
  opt.series = opt.series.map((s: any) => ({
    ...s,
    smooth: true,
  }));
  return opt;
}

function areaOption() {
  const opt = basicLineOption();
  opt.series = opt.series.map((s: any, i: number) => ({
    ...s,
    smooth: true,
    areaStyle: { opacity: 0.25 },
  }));
  return opt;
}

function stackedAreaOption() {
  const opt = basicLineOption();
  opt.series = opt.series.map((s: any) => ({
    ...s,
    smooth: true,
    stack: "total",
    areaStyle: { opacity: 0.4 },
    emphasis: { focus: "series" },
  }));
  return opt;
}

function stepLineOption() {
  const opt = basicLineOption();
  (opt.xAxis as any).boundaryGap = true;
  opt.series = opt.series.map((s: any) => ({
    ...s,
    step: "middle",
  }));
  return opt;
}

function barLineOption() {
  const cats = getCategories();
  const cols = getValueColumns();

  // First column as bars, remaining columns as lines
  const barCols = cols.slice(0, 1);
  const lineCols = cols.slice(1);

  const series: any[] = barCols.map((col) => ({
    name: col,
    type: "bar",
    data: getSeriesData(col),
  }));

  lineCols.forEach((col) => {
    series.push({
      name: col,
      type: "line",
      data: getSeriesData(col),
      smooth: true,
      symbol: "circle",
      symbolSize: 6,
    });
  });

  // If only one value column, duplicate it as both bar and line
  if (cols.length === 1) {
    series.push({
      name: cols[0] + " (trend)",
      type: "line",
      data: getSeriesData(cols[0]),
      smooth: true,
      symbol: "circle",
      symbolSize: 6,
    });
  }

  return {
    ...baseOption(),
    xAxis: {
      type: "category",
      data: cats,
      axisLabel: {
        ...axisLabelStyle(),
        rotate: cats.length > 10 ? 35 : 0,
      },
    },
    yAxis: {
      type: "value",
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    series,
  };
}

// ---------------------------------------------------------------------------
// Pie chart option builders
// ---------------------------------------------------------------------------

function pieOption() {
  const cats = getCategories();
  const cols = getValueColumns();
  const values = getSeriesData(cols[0]);

  return {
    tooltip: {
      trigger: "item",
      formatter: "{b}: {c} ({d}%)",
    },
    legend: {
      type: "scroll",
      bottom: 0,
      textStyle: { color: isDark ? "#a0a0b0" : "#666", fontSize: 12 },
    },
    color: COLORS,
    series: [
      {
        type: "pie",
        radius: "60%",
        center: ["50%", "50%"],
        data: cats.map((name, i) => ({ name, value: values[i] })),
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: "rgba(0, 0, 0, 0.5)",
          },
        },
        label: {
          color: isDark ? "#ccc" : "#333",
          fontSize: 12,
        },
      },
    ],
  };
}

function doughnutOption() {
  const opt = pieOption();
  (opt.series[0] as any).radius = ["35%", "60%"];
  return opt;
}

function roseOption() {
  const opt = pieOption();
  const s = opt.series[0] as any;
  s.radius = ["20%", "60%"];
  s.roseType = "area";
  return opt;
}

// ---------------------------------------------------------------------------
// Scatter chart option builders
// ---------------------------------------------------------------------------

function scatterOption() {
  const { numbers, strings } = getColumns();
  const xCol = numbers[0] || getValueColumns()[0];
  const yCol = numbers.length >= 2 ? numbers[1] : xCol;

  if (numbers.length < 2) {
    // Fallback: use row index as X, single numeric column as Y
    const data = getSeriesData(xCol).map((v, i) => [i, v]);
    return {
      ...baseOption(),
      tooltip: { trigger: "item" },
      xAxis: {
        type: "value",
        name: "Index",
        nameLocation: "middle" as const,
        nameGap: 30,
        axisLabel: axisLabelStyle(),
        splitLine: splitLineStyle(),
      },
      yAxis: {
        type: "value",
        name: xCol,
        nameLocation: "middle" as const,
        nameGap: 40,
        axisLabel: axisLabelStyle(),
        splitLine: splitLineStyle(),
      },
      series: [
        { name: xCol, type: "scatter", data, symbolSize: 10 },
      ],
    };
  }

  const xData = getSeriesData(xCol);
  const yData = getSeriesData(yCol);
  const groupCol = strings.length > 0 ? getXColumn() : null;

  if (groupCol) {
    const groups: Record<string, number[][]> = {};
    currentData.forEach((row, i) => {
      const key = String(row[groupCol]);
      if (!groups[key]) groups[key] = [];
      groups[key].push([xData[i], yData[i]]);
    });
    return {
      ...baseOption(),
      tooltip: { trigger: "item" },
      xAxis: {
        type: "value",
        name: xCol,
        nameLocation: "middle" as const,
        nameGap: 30,
        axisLabel: axisLabelStyle(),
        splitLine: splitLineStyle(),
      },
      yAxis: {
        type: "value",
        name: yCol,
        nameLocation: "middle" as const,
        nameGap: 40,
        axisLabel: axisLabelStyle(),
        splitLine: splitLineStyle(),
      },
      series: Object.entries(groups).map(([name, data]) => ({
        name,
        type: "scatter",
        data,
        symbolSize: 10,
      })),
    };
  }

  const data = xData.map((x, i) => [x, yData[i]]);
  return {
    ...baseOption(),
    tooltip: { trigger: "item" },
    xAxis: {
      type: "value",
      name: xCol,
      nameLocation: "middle" as const,
      nameGap: 30,
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    yAxis: {
      type: "value",
      name: yCol,
      nameLocation: "middle" as const,
      nameGap: 40,
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    series: [
      { name: `${xCol} vs ${yCol}`, type: "scatter", data, symbolSize: 10 },
    ],
  };
}

function bubbleOption() {
  const { numbers, strings } = getColumns();

  // Need at least 3 numeric columns for bubble (x, y, size)
  if (numbers.length < 3) return scatterOption();

  const xCol = numbers[0];
  const yCol = numbers[1];
  const sizeCol = numbers[2];
  const xData = getSeriesData(xCol);
  const yData = getSeriesData(yCol);
  const sizeData = getSeriesData(sizeCol);

  const maxSize = Math.max(...sizeData);
  const minSize = Math.min(...sizeData);
  const sizeRange = maxSize - minSize || 1;
  const sizeFn = (val: number[]) => 5 + ((val[2] - minSize) / sizeRange) * 45;

  const tooltipFmt = (params: any) => {
    const d = params.data;
    return `${params.seriesName}<br/>${xCol}: ${d[0]}<br/>${yCol}: ${d[1]}<br/>${sizeCol}: ${d[2]}`;
  };

  const groupCol = strings.length > 0 ? getXColumn() : null;

  if (groupCol) {
    const groups: Record<string, number[][]> = {};
    currentData.forEach((row, i) => {
      const key = String(row[groupCol]);
      if (!groups[key]) groups[key] = [];
      groups[key].push([xData[i], yData[i], sizeData[i]]);
    });
    return {
      ...baseOption(),
      tooltip: { trigger: "item", formatter: tooltipFmt },
      xAxis: {
        type: "value",
        name: xCol,
        nameLocation: "middle" as const,
        nameGap: 30,
        axisLabel: axisLabelStyle(),
        splitLine: splitLineStyle(),
      },
      yAxis: {
        type: "value",
        name: yCol,
        nameLocation: "middle" as const,
        nameGap: 40,
        axisLabel: axisLabelStyle(),
        splitLine: splitLineStyle(),
      },
      series: Object.entries(groups).map(([name, data]) => ({
        name,
        type: "scatter",
        data,
        symbolSize: sizeFn,
      })),
    };
  }

  const data = xData.map((x, i) => [x, yData[i], sizeData[i]]);
  return {
    ...baseOption(),
    tooltip: { trigger: "item", formatter: tooltipFmt },
    xAxis: {
      type: "value",
      name: xCol,
      nameLocation: "middle" as const,
      nameGap: 30,
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    yAxis: {
      type: "value",
      name: yCol,
      nameLocation: "middle" as const,
      nameGap: 40,
      axisLabel: axisLabelStyle(),
      splitLine: splitLineStyle(),
    },
    series: [
      {
        name: `${xCol} vs ${yCol}`,
        type: "scatter",
        data,
        symbolSize: sizeFn,
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function renderChart() {
  if (!currentData.length) return;

  const chartType = chartTypeSelect.value;

  const builders: Record<string, () => any> = {
    // Bar charts
    basic: basicBarOption,
    grouped: basicBarOption,
    stacked: stackedBarOption,
    horizontal: horizontalBarOption,
    "stacked-horizontal": stackedHorizontalOption,
    sorted: sortedBarOption,
    waterfall: waterfallOption,
    rounded: roundedBarOption,
    polar: polarBarOption,
    // Line charts
    "line-basic": basicLineOption,
    "line-smooth": smoothLineOption,
    "line-area": areaOption,
    "line-stacked-area": stackedAreaOption,
    "line-step": stepLineOption,
    // Mixed
    "bar-line": barLineOption,
    // Pie charts
    pie: pieOption,
    doughnut: doughnutOption,
    rose: roseOption,
    // Scatter charts
    scatter: scatterOption,
    bubble: bubbleOption,
  };

  const build = builders[chartType] || basicBarOption;
  const option = build();

  // Restore visibility, show card + header, clear any status message
  document.body.style.overflow = "";
  document.body.style.height = "";
  document.body.style.padding = "";
  cardEl.style.display = "";
  cardHeaderEl.style.display = "";
  cardTitleEl.textContent = currentTitle;
  chartEl.style.height = "480px";
  const existing = chartEl.querySelector(".status-message");
  if (existing) existing.remove();

  if (!chartInstance) {
    chartInstance = echarts.init(chartEl, isDark ? "dark" : undefined);
  }

  chartInstance.clear();
  chartInstance.setOption(option);
}
