import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Global drag/drop guard:
// Prevent the browser from opening dropped files (new tab/navigation),
// while still allowing our in-app dropzones (e.g. ChatWidget) to handle the files.
const _dndOptions: AddEventListenerOptions = { capture: true, passive: false };
const _preventBrowserFileOpen: EventListener = (evt) => {
  const e = evt as DragEvent;
  // Chrome will also navigate/open a new tab when dropping an image/URL ("text/uri-list").
  // We block the default for both files and URI drags.
  const dt = e.dataTransfer;
  const hasPayload =
    !!dt &&
    ((dt.types && Array.from(dt.types).includes("Files")) ||
      (dt.types && Array.from(dt.types).includes("text/uri-list")) ||
      (dt.files && dt.files.length > 0) ||
      (dt.items && Array.from(dt.items).some((it) => it.kind === "file")));
  if (!hasPayload) return;
  e.preventDefault();
  // IMPORTANT: don't stopPropagation — we still want in-app dropzones (ChatWidget)
  // to receive the drop event and process uploads.
};

// Install on both document + window to ensure it fires
// even when the drop target is outside React's root tree.
for (const target of [document, window] as const) {
  target.addEventListener("dragenter", _preventBrowserFileOpen, _dndOptions);
  target.addEventListener("dragover", _preventBrowserFileOpen, _dndOptions);
  target.addEventListener("drop", _preventBrowserFileOpen, _dndOptions);
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
