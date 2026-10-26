import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import "../workstation/design/tokens.css";
import "../workstation/design/primitives.css";
import "./companion.css";
import "./watch-workbench.css";
import { Companion } from "./Companion";

const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode><QueryClientProvider client={client}><Companion /></QueryClientProvider></React.StrictMode>,
);
