// A sheet that rests as a strip on the bottom of the map and pulls up from there, in three heights: swipe
// or tap the grip up to open it a step, down to close a step, and sideways on the open sheet to move to
// the next tab. Every swipe has a tap: the grip cycles the height. The same pattern as the NYC map agent's
// pull-up sheet, so the two apps feel alike under the thumb.

import { useEffect, useRef, type PointerEvent as ReactPointerEvent, type ReactNode, type TouchEvent as ReactTouchEvent } from "react";
import { nextLevel, swipeOf, type SheetLevel } from "@/lib/sheetSwipe";
import { cn } from "@/lib/utils";

const HEIGHT: Record<SheetLevel, string> = {
  0: "h-[5.25rem]",
  1: "h-[46dvh]",
  2: "h-[calc(100dvh-8.5rem)]",
};

export default function PullSheet({
  level,
  onLevel,
  onSide,
  onHeight,
  header,
  children,
  label,
  bare = false,
}: {
  level: SheetLevel;
  onLevel: (level: SheetLevel) => void;
  /** A sideways swipe on the open sheet: the next tab either way. */
  onSide?: (swipe: "left" | "right") => void;
  /** Reports the sheet's height in pixels, so the map can keep its own centre clear of it. */
  onHeight?: (px: number) => void;
  /** The row that rests on the strip: the tabs. */
  header: ReactNode;
  children: ReactNode;
  label: string;
  /** No padding or scrolling of its own, for content that brings both. */
  bare?: boolean;
}) {
  const root = useRef<HTMLElement | null>(null);
  const swiped = useRef(false);
  const touch = useRef<{ x: number; y: number; top: number } | null>(null);

  useEffect(() => {
    const element = root.current;
    if (!element || !onHeight) return;
    const report = () => onHeight(Math.ceil(element.getBoundingClientRect().height));
    report();
    const watch = new ResizeObserver(report);
    watch.observe(element);
    // The height animates, so the map follows it frame by frame rather than jumping at the end.
    element.addEventListener("transitionend", report);
    return () => {
      watch.disconnect();
      element.removeEventListener("transitionend", report);
      onHeight(0);
    };
  }, [onHeight]);

  const pull = (event: ReactPointerEvent) => {
    swiped.current = false;
    const from = { x: event.clientX, y: event.clientY };
    const up = (ev: PointerEvent) => {
      window.removeEventListener("pointerup", up);
      const swipe = swipeOf(ev.clientX - from.x, ev.clientY - from.y);
      if (swipe !== "up" && swipe !== "down") return;
      swiped.current = true;
      onLevel(nextLevel(level, swipe));
    };
    window.addEventListener("pointerup", up);
  };

  const bodyStart = (event: ReactTouchEvent<HTMLDivElement>) => {
    const t = event.touches[0];
    touch.current = { x: t.clientX, y: t.clientY, top: event.currentTarget.scrollTop };
  };
  const bodyEnd = (event: ReactTouchEvent<HTMLDivElement>) => {
    const start = touch.current;
    touch.current = null;
    if (!start) return;
    const t = event.changedTouches[0];
    const swipe = swipeOf(t.clientX - start.x, t.clientY - start.y);
    if (swipe === "left" || swipe === "right") onSide?.(swipe);
    // A downward swipe on a body that is already at its top hands the gesture to the sheet.
    else if (swipe === "down" && start.top <= 0) onLevel(nextLevel(level, "down"));
  };

  return (
    <section
      ref={root}
      aria-label={label}
      className={cn(
        "absolute inset-x-0 bottom-0 z-20 flex flex-col overflow-hidden rounded-t-3xl border-t border-border bg-background shadow-[0_-10px_36px_rgba(2,6,23,0.35)] transition-[height] duration-300 ease-out motion-reduce:transition-none",
        HEIGHT[level],
      )}
    >
      <div onPointerDown={pull} className="shrink-0 touch-none">
        <button
          type="button"
          aria-label={level === 2 ? "Show less" : "Show more"}
          aria-expanded={level > 0}
          onClick={() => {
            if (swiped.current) swiped.current = false;
            else onLevel(level === 2 ? 0 : ((level + 1) as SheetLevel));
          }}
          className="flex h-7 w-full items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span aria-hidden="true" className="h-1.5 w-10 rounded-full bg-muted-foreground/40" />
        </button>
        {header}
      </div>
      <div
        onTouchStart={bodyStart}
        onTouchEnd={bodyEnd}
        className={cn("min-h-0 flex-1", bare ? "overflow-hidden" : "overflow-y-auto overscroll-contain px-4 pb-8 pt-3")}
      >
        {children}
      </div>
    </section>
  );
}
