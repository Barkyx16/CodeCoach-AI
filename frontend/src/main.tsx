import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { AppProviders } from "./app/providers";
import { makeQueryClient } from "./app/queryClient";
import { createRouter } from "./app/router";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";
import "./styles/layout.css";
import "./styles/features.css";
import "./styles/landing.css";
import "./styles/details.css";
import "./styles/settings.css";
import "./styles/careers.css";
import "./styles/voice.css";
import "./styles/progress.css";
import "./styles/plan.css";
import "./styles/targets.css";
import "./styles/review.css";
import "./styles/saved.css";
import "./styles/learn.css";
import "./styles/notes.css";

const queryClient = makeQueryClient();
const router = createRouter();

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
);
