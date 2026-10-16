import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);

// Splash screen (markup + styles live in index.html, so it paints before any JS runs --
// no flash of a blank page). Shown for a minimum time so it reads as a deliberate brand
// moment rather than a flicker, then fades out and is removed from the DOM.
const splash = document.getElementById("splash");
if (splash) {
  window.setTimeout(() => {
    splash.classList.add("hide");
    window.setTimeout(() => splash.remove(), 500);
  }, 700);
}

// Offline app shell (production builds only, so it never interferes with the dev server)
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
