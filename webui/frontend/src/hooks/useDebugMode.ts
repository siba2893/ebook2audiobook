import { useEffect, useState } from "react";

const KEY = "ebook2audiobook:debug_mode";
const EVENT = "debug-mode-change";

export function useDebugMode(): [boolean, (v: boolean) => void] {
  const [enabled, setEnabled] = useState<boolean>(() => localStorage.getItem(KEY) === "1");

  useEffect(() => {
    // Cross-tab via storage event; same-tab via custom event.
    const sync = () => setEnabled(localStorage.getItem(KEY) === "1");
    window.addEventListener("storage", sync);
    window.addEventListener(EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(EVENT, sync);
    };
  }, []);

  const setDebug = (v: boolean) => {
    localStorage.setItem(KEY, v ? "1" : "0");
    setEnabled(v);
    window.dispatchEvent(new Event(EVENT));
  };

  return [enabled, setDebug];
}
