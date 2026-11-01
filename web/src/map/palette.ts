// The colours the map paints with. WebGL paint values are plain strings, so the map's data encoding
// cannot come from the Tailwind tokens the rest of the app uses; these constants are the single
// source of truth for both the pins/links drawn on the canvas and the legend drawn over it.
//
// The map is a dark canvas whatever the page theme is, so every colour here is chosen to glow on it.

import type { ArcType, Category } from "@/lib/citations";

export const CATEGORY_COLORS: Record<Category, string> = {
  county: "#60a5fa",
  state: "#a78bfa",
  statute: "#2dd4bf",
  federal: "#fbbf24",
};

export const CATEGORY_LABELS: Record<Category, string> = {
  county: "County court",
  state: "Colorado court",
  statute: "Colorado statute",
  federal: "Federal",
};

export const ARC_COLORS: Record<ArcType, string> = {
  cc: "#60a5fa",
  cs: "#a78bfa",
  st: "#2dd4bf",
  fed: "#fbbf24",
  other: "#94a3b8",
};

export const ARC_LABELS: Record<ArcType, string> = {
  cc: "County to county",
  cs: "County to state",
  st: "Statute",
  fed: "Federal",
  other: "Link",
};

/** The ground under the pins: land, water, the state shape and the lines that divide it. */
export const GROUND = {
  land: "#0c1322",
  water: "#060a14",
  green: "#0f1a2c",
  road: "#1e2a44",
  /** Colorado, lifted a step above the land so the state the law comes from reads first. */
  state: "#16223d",
  stateLine: "#4f6aa3",
  border: "#33415f",
  country: "#52618a",
  label: "#7d8db0",
  labelHalo: "#0c1322",
};

/**
 * Counties and the walked path. County lines are dashed and dim, so they read as a division of land
 * rather than a route; the walked path is inked white like a graph edge, because that is what it is.
 */
export const CONTEXT_COLORS = {
  county: "#6b7fae",
  countyLabel: "#8da0c8",
  /** The path the tour has walked so far, and its arrowheads. */
  trail: "#f8fafc",
  trailGlow: "#a5b4fc",
};
