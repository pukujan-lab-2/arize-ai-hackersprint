// A swipe on a sheet: which way it went, or null for a tap or a wobble. The same small rules the NYC map
// agent's pull-up sheet uses, so the two apps feel alike under the thumb. Pure, so they can be tested.

export type Swipe = "up" | "down" | "left" | "right";

const MIN_PX = 36;

/** One direction must clearly win, by 1.3×, so a diagonal drag does nothing. */
export function swipeOf(dx: number, dy: number): Swipe | null {
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  if (ay >= MIN_PX && ay > ax * 1.3) return dy < 0 ? "up" : "down";
  if (ax >= MIN_PX && ax > ay * 1.3) return dx < 0 ? "left" : "right";
  return null;
}

/** Sheet heights: 0 is the strip that rests on the map, 1 the open sheet, 2 the tallest that still shows the map. */
export type SheetLevel = 0 | 1 | 2;

/** Up opens one step, down closes one step. */
export function nextLevel(level: SheetLevel, swipe: "up" | "down"): SheetLevel {
  if (swipe === "up") return level === 2 ? 2 : ((level + 1) as SheetLevel);
  return level === 0 ? 0 : ((level - 1) as SheetLevel);
}

/** Left steps forward and right steps back through the tabs, wrapping round at the ends. */
export function nextTab<T>(tabs: readonly T[], at: T, swipe: "left" | "right"): T {
  const i = Math.max(0, tabs.indexOf(at));
  return tabs[(i + (swipe === "left" ? 1 : tabs.length - 1)) % tabs.length];
}
