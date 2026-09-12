import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { SettingsProvider } from "./game/settings";
import { UserProvider } from "./game/auth";
import "./styles/theme.css";
import "./styles/table.css";
import "./styles/cards.css";
import "./styles/panels.css";
import "./styles/explorer.css";
import "./styles/bugs.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SettingsProvider>
      <UserProvider>
        <App />
      </UserProvider>
    </SettingsProvider>
  </React.StrictMode>,
);
