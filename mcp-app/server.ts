import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  registerAppTool,
  registerAppResource,
  RESOURCE_MIME_TYPE,
} from "@modelcontextprotocol/ext-apps/server";
import { z } from "zod";
import fs from "node:fs/promises";
import path from "node:path";

const server = new McpServer({
  name: "Teradata Query Visualizer",
  version: "1.0.0",
});

const resourceUri = "ui://visualize-query/mcp-app.html";

// Resolve dist directory: when running as .ts (dev) look in ./dist,
// when running as compiled .js (prod) look in same directory
const DIST_DIR = import.meta.filename.endsWith(".ts")
  ? path.join(import.meta.dirname, "dist")
  : import.meta.dirname;

// Register the visualization tool with UI metadata
registerAppTool(
  server,
  "visualize_query",
  {
    title: "Visualize Query Results",
    description: `Renders Teradata query results as interactive ECharts bar charts with a dropdown to select different chart styles (Basic, Grouped, Stacked, Horizontal, Waterfall, Sorted, Rounded, Polar).

Pass the query results as a JSON array of objects where each object represents a row with column names as keys.

Example input for data parameter:
[{"region": "East", "sales": 1200, "profit": 300}, {"region": "West", "sales": 950, "profit": 200}]

The visualization auto-detects categorical columns (strings) for the X-axis and numeric columns for the Y-axis values. Users can switch chart types and select the X-axis column via dropdowns.`,
    inputSchema: {
      data: z
        .string()
        .describe(
          'Query results as a JSON array of objects, e.g. [{"name": "A", "value": 10}]',
        ),
      title: z
        .string()
        .optional()
        .describe("Chart title (defaults to 'Query Results')"),
    },
    _meta: {
      ui: {
        resourceUri,
        csp: {
          "script-src": ["https://cdn.jsdelivr.net"],
        },
      },
    },
  },
  async ({ data, title }) => {
    let parsedData: unknown[];
    try {
      parsedData = JSON.parse(data);
    } catch {
      return {
        content: [
          {
            type: "text" as const,
            text: "Error: Invalid JSON data. Please provide a valid JSON array of objects.",
          },
        ],
      };
    }

    if (!Array.isArray(parsedData) || parsedData.length === 0) {
      return {
        content: [
          {
            type: "text" as const,
            text: "Error: Data must be a non-empty JSON array of objects.",
          },
        ],
      };
    }

    const chartTitle = title || "Query Results";

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({ data: parsedData, title: chartTitle }),
        },
      ],
    };
  },
);

// Register the HTML resource that serves the bundled ECharts UI
registerAppResource(
  server,
  resourceUri,
  resourceUri,
  { mimeType: RESOURCE_MIME_TYPE },
  async () => {
    const html = await fs.readFile(
      path.join(DIST_DIR, "mcp-app.html"),
      "utf-8",
    );
    return {
      contents: [
        { uri: resourceUri, mimeType: RESOURCE_MIME_TYPE, text: html },
      ],
    };
  },
);

// Start the server with stdio transport
const transport = new StdioServerTransport();
await server.connect(transport);
