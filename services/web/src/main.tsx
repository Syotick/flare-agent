import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createTheme, MantineProvider } from "@mantine/core";
import App from "./App";
import "@mantine/core/styles.css";
import "./styles.css";

// Flare 耀斑主题：amber 主色 + 深色表面 + 圆角
const theme = createTheme({
  primaryColor: "flare",
  primaryShade: 6,
  defaultRadius: "md",
  colors: {
    flare: [
      "#fff5ec",
      "#ffe7d2",
      "#ffcfa3",
      "#ffb673",
      "#ff9f4a",
      "#ff8f2e",
      "#f57a1c",
      "#d95f0e",
      "#b0490a",
      "#7c3106",
    ],
    dark: [
      "#f4f4f5",
      "#e6e6e8",
      "#d5d5d9",
      "#a6a6ad",
      "#73737d",
      "#55555e",
      "#3f3f47",
      "#27272c",
      "#1a1a1f",
      "#0e0e12",
    ],
  },
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Roboto, sans-serif',
  fontFamilyMonospace:
    'ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", Consolas, monospace',
  headings: { fontWeight: "650" },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <App />
    </MantineProvider>
  </StrictMode>
);
