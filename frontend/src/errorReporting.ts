import { API_BASE_URL } from "./config/api";

function reportError(message: string, stack?: string) {
  const body = JSON.stringify({ message: message.slice(0, 2000), stack: stack?.slice(0, 8000), url: window.location.href });
  const url = `${API_BASE_URL}/client-errors`;
  if (navigator.sendBeacon) {
    navigator.sendBeacon(url, new Blob([body], { type: "application/json" }));
  } else {
    fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => {});
  }
}

export function installErrorReporting() {
  window.addEventListener("error", (event) => {
    reportError(event.message, event.error?.stack);
  });
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    const message = reason instanceof Error ? reason.message : String(reason);
    reportError(message, reason instanceof Error ? reason.stack : undefined);
  });
}
