import { useEffect, useState } from "react";

/** True while the window is at least `px` wide, so a side column can sit beside the chat instead of over it. */
export function useWide(px = 1024): boolean {
  return useMedia(`(min-width: ${px}px)`);
}

/** Whether a media query matches right now, and keeps matching as the window turns or resizes. */
export function useMedia(query: string): boolean {
  const [wide, setWide] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setWide(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return wide;
}
