"use client";
import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#6c8cff" },
    error: { main: "#f04a5a" },
    success: { main: "#3fb57a" },
    background: { default: "#0f1117", paper: "#1a1d27" },
    text: { primary: "#e1e4ed", secondary: "#888ca6" },
    divider: "#2e3347",
  },
  shape: { borderRadius: 8 },
  typography: { fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' },
});

export default theme;
