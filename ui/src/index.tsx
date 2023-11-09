import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter as Router } from "react-router-dom";
import Navigation from "components/Navigation";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./sass/styles.scss";
import { NotificationProvider } from "@canonical/react-components";

const queryClient = new QueryClient();

const rootElement = document.getElementById("app");
if (!rootElement) throw new Error("Failed to find the root element");
const root = createRoot(rootElement);
root.render(
  <Router>
    <QueryClientProvider client={queryClient}>
      <NotificationProvider>
        <div className="l-application" role="presentation">
          <Navigation />
          <main className="l-main">
            <App />
          </main>
        </div>
      </NotificationProvider>
    </QueryClientProvider>
  </Router>,
);
