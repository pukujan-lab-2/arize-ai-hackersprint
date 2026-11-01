// The map: MapLibre GL JS over a dark vector basemap, with one glowing pin per place an answer's
// authorities sit in and one curved arc per link between them. The tour flies the camera from the
// whole country down to each court in turn, tilted, while the walked path is inked over the links.
//
// Three things here are deliberate. The style is written out in this file, with the tile server named
// as a source, rather than fetched as a style document, so the map has a valid style the instant it is
// created and never sits blank waiting on somebody else's server. The pins are DOM markers, so they are
// there whatever the tiles do. And Colorado is drawn from the Census's own county boundaries on top of
// the basemap, so if the tiles never arrive the pane still shows the state the law comes from.
//
// Pins that would land on top of each other at the current zoom collapse into one numbered pin; a click
// on it zooms to the places inside it. That is what keeps a country-wide answer readable.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Box, KeyRound, LocateFixed } from "lucide-react";
import { Button } from "@/components/ui/button";
import { arcType, locate, type Citation, type Edge, type Location } from "@/lib/citations";
import { ARC_COLORS, ARC_LABELS, CATEGORY_COLORS, CATEGORY_LABELS, CONTEXT_COLORS, GROUND } from "@/map/palette";
import { cn } from "@/lib/utils";

/** The authorities that resolve to one place on the map. */
export type MapPlace = { key: string; label: string; citations: Citation[] };

type Pin = {
  key: string;
  label: string;
  loc: Location;
  lngLat: [number, number];
  citations: Citation[];
};

/** The whole country, the frame every walk starts from and every empty answer rests on. */
const US_CENTER: [number, number] = [-97.5, 38.8];
const US_ZOOM = 3.4;

/** Colorado, low enough that the state sits in the middle of the pane before the pins are fitted. */
const CENTER: [number, number] = [-105.55, 39.0];

/** How steeply the camera leans while the tour flies, and when the reader asks for the tilt. */
const TILT = 52;

/** Pins closer than this on screen, in pixels, share one numbered pin. */
const CLUSTER_PX = 34;

const TILE_JSON = "https://tiles.openfreemap.org/planet";
const GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
const FONT = ["Noto Sans Regular"];
const FONT_BOLD = ["Noto Sans Bold"];
const NAME: maplibregl.ExpressionSpecification = ["coalesce", ["get", "name:en"], ["get", "name"]];

/**
 * The basemap, written here rather than fetched. One vector source (OpenFreeMap, keyless) carries the
 * water, the land cover, the country and state borders, the main roads and the place names; every
 * layer below is drawn dark and dim, so the pins and arcs are the only bright things on the page.
 */
const basemap = (): maplibregl.StyleSpecification => ({
  version: 8,
  glyphs: GLYPHS,
  sources: {
    openmaptiles: {
      type: "vector",
      url: TILE_JSON,
      attribution:
        '<a href="https://openfreemap.org" target="_blank" rel="noopener noreferrer">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener noreferrer">OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>',
    },
  },
  layers: [
    { id: "ground", type: "background", paint: { "background-color": GROUND.land } },
    {
      id: "landcover",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "landcover",
      filter: ["in", ["get", "class"], ["literal", ["wood", "grass", "farmland"]]],
      paint: { "fill-color": GROUND.green, "fill-opacity": 0.8 },
    },
    {
      id: "water",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "water",
      paint: { "fill-color": GROUND.water },
    },
    {
      id: "roads",
      type: "line",
      source: "openmaptiles",
      "source-layer": "transportation",
      minzoom: 5.5,
      filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk"]]],
      paint: {
        "line-color": GROUND.road,
        "line-width": ["interpolate", ["linear"], ["zoom"], 5.5, 0.4, 10, 1.4],
      },
    },
    {
      id: "state-border",
      type: "line",
      source: "openmaptiles",
      "source-layer": "boundary",
      filter: ["all", ["==", ["get", "admin_level"], 4], ["!=", ["get", "maritime"], 1]],
      paint: { "line-color": GROUND.border, "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 8, 1.4] },
    },
    {
      id: "country-border",
      type: "line",
      source: "openmaptiles",
      "source-layer": "boundary",
      filter: ["all", ["==", ["get", "admin_level"], 2], ["!=", ["get", "maritime"], 1]],
      paint: { "line-color": GROUND.country, "line-width": ["interpolate", ["linear"], ["zoom"], 2, 0.8, 8, 1.8] },
    },
    {
      id: "state-name",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "place",
      minzoom: 3,
      maxzoom: 7,
      filter: ["==", ["get", "class"], "state"],
      layout: {
        "text-font": FONT,
        "text-field": NAME,
        "text-size": ["interpolate", ["linear"], ["zoom"], 3, 9, 6, 13],
        "text-transform": "uppercase",
        "text-letter-spacing": 0.14,
        "text-max-width": 8,
      },
      paint: { "text-color": GROUND.label, "text-halo-color": GROUND.labelHalo, "text-halo-width": 1.5, "text-opacity": 0.7 },
    },
    {
      id: "city-name",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "place",
      minzoom: 4.5,
      filter: ["in", ["get", "class"], ["literal", ["city", "town"]]],
      layout: {
        "text-font": FONT,
        "text-field": NAME,
        "text-size": ["interpolate", ["linear"], ["zoom"], 4.5, 10, 12, 14],
        "text-max-width": 7,
        "text-padding": 6,
      },
      paint: { "text-color": GROUND.label, "text-halo-color": GROUND.labelHalo, "text-halo-width": 1.4 },
    },
  ],
});

/**
 * The counties. Only Colorado is kept, so the map is Colorado's map: the fill lifts the state a step
 * above the land, the dashed lines divide it, and each county carries its name once the camera is close.
 * The Census's own boundaries are public domain, keyless, and served over a CDN.
 */
const COUNTY_URL = "https://cdn.jsdelivr.net/gh/plotly/datasets@master/geojson-counties-fips.json";
const COUNTY_SOURCE = "co-counties";
const COUNTY_FILL = "co-fill";
const COUNTY_EDGE = "co-edge";
const COUNTY_LINE = "co-county-line";
const COUNTY_NAME = "co-county-name";

/**
 * Colorado's own bounds, in lng/lat. An authority outside them — the U.S. Code, a circuit court, the
 * Supreme Court — is real and worth a pin, but fitting the camera to it as well drags the whole state
 * down to a smudge in the middle of the country, where nothing can be read. So the camera fits the
 * state's own authorities, and the out-of-state ones are a pan away.
 */
const CO_BOUNDS: [number, number, number, number] = [-109.1, 36.9, -102.0, 41.1];

const inColorado = (pin: Pin) =>
  pin.lngLat[0] >= CO_BOUNDS[0] &&
  pin.lngLat[0] <= CO_BOUNDS[2] &&
  pin.lngLat[1] >= CO_BOUNDS[1] &&
  pin.lngLat[1] <= CO_BOUNDS[3];

/** One download for the whole page: every mount, and every style reload, reads the same promise. */
let counties: Promise<GeoJSON.FeatureCollection | null> | null = null;

function coloradoCounties(): Promise<GeoJSON.FeatureCollection | null> {
  if (counties) return counties;
  counties = fetch(COUNTY_URL)
    .then((response) => (response.ok ? (response.json() as Promise<GeoJSON.FeatureCollection>) : null))
    .then((all) => {
      if (!all?.features) return null;
      const features = all.features.filter(
        (feature) => String((feature.properties as { STATE?: string } | null)?.STATE) === "08",
      );
      return features.length ? ({ type: "FeatureCollection", features } as GeoJSON.FeatureCollection) : null;
    })
    .catch(() => null);
  return counties;
}

const TRAIL = "trail";
const ARROW = "trail-arrow";

/**
 * A quadratic arc between two places. It is bowed to the left of a→b, so the two directions of one link
 * never lie on top of each other, and it is measured in locally scaled degrees so a long link does not
 * bow further off the page than a short one.
 */
function curve(a: [number, number], b: [number, number]): [number, number][] {
  const k = Math.cos((((a[1] + b[1]) / 2) * Math.PI) / 180) || 1;
  const ax = a[0] * k;
  const ay = a[1];
  const bx = b[0] * k;
  const by = b[1];
  const dx = bx - ax;
  const dy = by - ay;
  const cx = (ax + bx) / 2 - dy * 0.14;
  const cy = (ay + by) / 2 + dx * 0.14;
  const points: [number, number][] = [];
  for (let i = 0; i <= 24; i += 1) {
    const t = i / 24;
    const u = 1 - t;
    points.push([(u * u * ax + 2 * u * t * cx + t * t * bx) / k, u * u * ay + 2 * u * t * cy + t * t * by]);
  }
  return points;
}

/** An arrowhead pointing right, drawn once on a canvas so the trail needs no sprite sheet or network. */
function addArrow(map: maplibregl.Map, color: string) {
  if (map.hasImage(ARROW)) return;
  const size = 32;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.fillStyle = color;
  context.beginPath();
  context.moveTo(3, 5);
  context.lineTo(size - 3, size / 2);
  context.lineTo(3, size - 5);
  context.closePath();
  context.fill();
  map.addImage(ARROW, context.getImageData(0, 0, size, size), { pixelRatio: 2 });
}

/** One pin per place: the authorities that resolve to the same court share it. */
function buildPins(citations: Citation[]): Pin[] {
  const places = new Map<string, Pin>();
  for (const citation of citations) {
    const loc = locate(citation);
    const existing = places.get(loc.key);
    if (existing) {
      existing.citations.push(citation);
      continue;
    }
    places.set(loc.key, {
      key: loc.key,
      label: loc.label,
      loc,
      lngLat: [loc.ll[1], loc.ll[0]],
      citations: [citation],
    });
  }
  return [...places.values()];
}

const reducedMotion = () => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** One empty list, shared, so a missing prop does not look like new data on every render. */
const NONE: never[] = [];

/**
 * What a pin says on the map: the court's name without the route to it or the seat's city, so
 * "Boulder County (Boulder) → Colorado Court of Appeals (Denver)" reads "Boulder County" and nothing is
 * cut off. The full label stays in the pin's tooltip and in the card it opens.
 */
function shortLabel(label: string): string {
  const first = label.split(" → ")[0] ?? label;
  return first.replace(/\s*\([^)]*\)\s*$/, "").trim() || label;
}

/** The glow a pin gives off, in its own colour: a tight halo and a soft bloom. */
const glow = (color: string) => `0 0 0 4px ${color}33, 0 0 18px 2px ${color}99`;

export default function CitationMap({
  citations = NONE,
  edges = NONE,
  focus = null,
  trail = NONE,
  onSelect,
  className,
}: {
  citations?: Citation[];
  edges?: Edge[];
  /** The place the tour is on, so the camera follows the voice. Null fits every authority. */
  focus?: string | null;
  /** The places the tour has walked so far, in order, so the graph shows its own traversal. */
  trail?: string[];
  onSelect: (place: MapPlace) => void;
  className?: string;
}) {
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markers = useRef<{ pin: Pin; marker: maplibregl.Marker }[]>([]);
  /** The pins each visible pin stands for at the current zoom, itself included. */
  const groups = useRef(new Map<string, Pin[]>());
  /** Bumped on every flight, so a flight that was interrupted does not start the one after it. */
  const flight = useRef(0);
  /** The place the tour was on when the pins were last arranged, so that place is never swallowed. */
  const lastFocus = useRef<string | null>(null);
  /** The place the camera last flew to, so the first stop of a walk can start from the whole country. */
  const lastFlightFocus = useRef<string | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [county, setCounty] = useState(false);
  const [tilted, setTilted] = useState(false);
  const [keyOpen, setKeyOpen] = useState(false);

  const pins = useMemo(() => buildPins(citations), [citations]);

  const fit = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const duration = reducedMotion() ? 0 : 900;
    if (!pins.length) {
      map.easeTo({ center: US_CENTER, zoom: US_ZOOM, pitch: 0, duration });
      return;
    }
    // Fit the state's own authorities; a lone federal pin in Washington does not get to decide the scale.
    const home = pins.filter(inColorado);
    const targets = home.length ? home : pins;
    if (targets.length === 1) {
      map.easeTo({ center: targets[0].lngLat, zoom: 9.2, pitch: 0, duration });
      return;
    }
    const bounds = new maplibregl.LngLatBounds();
    for (const pin of targets) bounds.extend(pin.lngLat);
    map.fitBounds(bounds, { padding: 72, maxZoom: 10, pitch: 0, duration });
  }, [pins]);

  // The map is created once; everything after this only updates its data. Rotation is off: a map that
  // can be twisted by accident is a map that is hard to get back. Tilt is on, but only through the
  // button and the tour, never by a stray drag.
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: element,
        style: basemap(),
        center: CENTER,
        zoom: 6,
        minZoom: 2.6,
        maxZoom: 16,
        maxPitch: 62,
        dragRotate: false,
        pitchWithRotate: false,
        renderWorldCopies: false,
        attributionControl: { compact: true },
      });
    } catch {
      setFailed(true);
      return;
    }
    mapRef.current = map;
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false, visualizePitch: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "imperial", maxWidth: 96 }), "bottom-left");

    // The style is written in this file, so it can be loaded before the listener below is attached;
    // check first, and only wait if there is something left to wait for.
    const onStyleLoad = () => setReady(true);
    map.on("style.load", onStyleLoad);
    if (map.isStyleLoaded()) setReady(true);
    const onPitch = () => setTilted(map.getPitch() > 8);
    map.on("pitchend", onPitch);

    // A map created before its pane has a height draws into nothing and stays blank until something
    // else resizes the window, so the pane is watched rather than assumed.
    const resize = new ResizeObserver(() => map.resize());
    resize.observe(element);

    return () => {
      resize.disconnect();
      map.off("style.load", onStyleLoad);
      map.off("pitchend", onPitch);
      for (const item of markers.current) item.marker.remove();
      markers.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // The counties: Colorado lifted off the land, outlined, divided and named. The outline of the state
  // falls out of the counties for free, because the outer edges of every county together are the state.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    let live = true;
    void coloradoCounties().then((data) => {
      if (!live || !data || !mapRef.current) return;
      if (!map.getSource(COUNTY_SOURCE)) map.addSource(COUNTY_SOURCE, { type: "geojson", data });
      // The counties belong under the citation links and the walked path, not over them, so they are
      // inserted beneath the links layer rather than simply appended.
      const before = map.getLayer("links-glow") ? "links-glow" : map.getLayer("links") ? "links" : undefined;
      if (!map.getLayer(COUNTY_FILL)) {
        map.addLayer(
          {
            id: COUNTY_FILL,
            type: "fill",
            source: COUNTY_SOURCE,
            paint: { "fill-color": GROUND.state, "fill-opacity": 0.95 },
          },
          before,
        );
      }
      if (!map.getLayer(COUNTY_LINE)) {
        map.addLayer(
          {
            id: COUNTY_LINE,
            type: "line",
            source: COUNTY_SOURCE,
            paint: {
              "line-color": CONTEXT_COLORS.county,
              "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.5, 9, 1, 14, 1.6],
              "line-dasharray": [2, 1.6],
              "line-opacity": ["interpolate", ["linear"], ["zoom"], 5, 0.15, 7, 0.75],
            },
          },
          before,
        );
      }
      // A soft halo on the state's whole edge: the county edges drawn thick and blurred under a crisp
      // line, so Colorado glows faintly against the dark land.
      if (!map.getLayer(COUNTY_EDGE)) {
        map.addLayer(
          {
            id: COUNTY_EDGE,
            type: "line",
            source: COUNTY_SOURCE,
            paint: {
              "line-color": GROUND.stateLine,
              "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.7, 8, 2],
              "line-opacity": 0.55,
              "line-blur": 0.6,
            },
          },
          before,
        );
      }
      if (!map.getLayer(COUNTY_NAME)) {
        map.addLayer(
          {
            id: COUNTY_NAME,
            type: "symbol",
            source: COUNTY_SOURCE,
            minzoom: 6.5,
            layout: {
              "text-font": FONT_BOLD,
              "text-field": ["get", "NAME"],
              "text-size": ["interpolate", ["linear"], ["zoom"], 6.5, 9.5, 12, 12],
              "text-letter-spacing": 0.14,
              "text-transform": "uppercase",
              "text-max-width": 8,
              "text-padding": 10,
            },
            paint: {
              "text-color": CONTEXT_COLORS.countyLabel,
              "text-halo-color": GROUND.labelHalo,
              "text-halo-width": 1.6,
              "text-opacity": 0.85,
            },
          },
          before,
        );
      }
      setCounty(true);
    });
    return () => {
      live = false;
    };
  }, [ready]);

  // At the scale of a country the pins land on top of one another, so those that would overlap on
  // screen share one numbered pin and the rest are hidden until the camera is close enough to part them.
  const declutter = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const kept: { pin: Pin; at: maplibregl.Point; members: Pin[] }[] = [];
    // The place the tour is on is never swallowed by a neighbour, and a bigger pin outranks a smaller.
    const ordered = [...markers.current].sort((a, b) => {
      const mine = (item: { pin: Pin }) => (item.pin.key === lastFocus.current ? 1 : 0);
      return mine(b) - mine(a) || b.pin.citations.length - a.pin.citations.length;
    });
    for (const item of ordered) {
      const at = map.project(item.pin.lngLat);
      const host = kept.find((other) => Math.hypot(other.at.x - at.x, other.at.y - at.y) < CLUSTER_PX);
      if (host) host.members.push(item.pin);
      else kept.push({ pin: item.pin, at, members: [item.pin] });
    }
    const hosts = new Map(kept.map((entry) => [entry.pin.key, entry.members] as const));
    groups.current = hosts;
    for (const { pin, marker } of markers.current) {
      const element = marker.getElement();
      const members = hosts.get(pin.key);
      element.style.display = members ? "" : "none";
      if (!members) continue;
      const total = members.reduce((sum, member) => sum + member.citations.length, 0);
      const dot = element.querySelector<HTMLElement>("[data-dot]");
      if (dot) dot.textContent = total > 1 ? String(total) : "";
      element.dataset.cluster = members.length > 1 ? "1" : "";
      const label = element.querySelector<HTMLElement>("[data-label]");
      if (label) {
        // A pin standing for several places carries its count in the dot, not a second name under it.
        label.textContent = shortLabel(pin.label);
        label.classList.toggle("hidden", members.length > 1 || map.getZoom() < 5.5);
        label.classList.remove("invisible");
      }
    }

    // Names are laid down in order of importance and a name that would land on one already placed, or on
    // another pin, is hidden until the camera is close enough to part them.
    const taken: DOMRect[] = [];
    for (const entry of kept) {
      const dot = markers.current.find((item) => item.pin.key === entry.pin.key)?.marker.getElement();
      const rect = dot?.querySelector<HTMLElement>("[data-dot]")?.getBoundingClientRect();
      if (rect) taken.push(rect);
    }
    for (const entry of kept) {
      const element = markers.current.find((item) => item.pin.key === entry.pin.key)?.marker.getElement();
      const label = element?.querySelector<HTMLElement>("[data-label]");
      if (!label || label.classList.contains("hidden")) continue;
      const box = label.getBoundingClientRect();
      const clash = taken.some(
        (other) =>
          box.left < other.right + 2 && box.right > other.left - 2 && box.top < other.bottom + 2 && box.bottom > other.top - 2,
      );
      if (clash) label.classList.add("invisible");
      else taken.push(box);
    }
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    // A link is drawn between the two pins its authorities sit on; a link inside one place is not a link.
    const pinOf = new Map<string, Pin>();
    for (const pin of pins) for (const citation of pin.citations) pinOf.set(citation.id, pin);
    const features: GeoJSON.Feature<GeoJSON.LineString, { arc: string }>[] = [];
    for (const edge of edges) {
      const from = pinOf.get(edge.src);
      const to = pinOf.get(edge.dst);
      if (!from || !to || from.key === to.key) continue;
      features.push({
        type: "Feature",
        properties: { arc: arcType(from.loc, to.loc) },
        geometry: { type: "LineString", coordinates: curve(from.lngLat, to.lngLat) },
      });
    }
    const data: GeoJSON.FeatureCollection<GeoJSON.LineString> = { type: "FeatureCollection", features };

    const source = map.getSource("links") as maplibregl.GeoJSONSource | undefined;
    if (source) {
      source.setData(data);
    } else {
      map.addSource("links", { type: "geojson", data });
      const color: maplibregl.ExpressionSpecification = [
        "match",
        ["get", "arc"],
        "cc",
        ARC_COLORS.cc,
        "cs",
        ARC_COLORS.cs,
        "st",
        ARC_COLORS.st,
        "fed",
        ARC_COLORS.fed,
        ARC_COLORS.other,
      ];
      // A wide, blurred copy under each line, so a link glows the way a pin does.
      map.addLayer({
        id: "links-glow",
        type: "line",
        source: "links",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": color,
          "line-width": ["interpolate", ["linear"], ["zoom"], 3, 4, 8, 7],
          "line-blur": 5,
          "line-opacity": 0.28,
        },
      });
      map.addLayer({
        id: "links",
        type: "line",
        source: "links",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": color,
          "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1.1, 8, 2],
          "line-opacity": 0.85,
        },
      });
      // The counties were drawn before the links existed; lift the links above them.
      for (const id of [COUNTY_FILL, COUNTY_LINE, COUNTY_EDGE, COUNTY_NAME]) {
        if (map.getLayer(id)) map.moveLayer(id, "links-glow");
      }
    }

    for (const item of markers.current) item.marker.remove();
    markers.current = pins.map((pin) => {
      // The dot is the marker and the court's name hangs under it, so the map says where each pin is
      // without a hover. The name is absolutely positioned, so it never moves the dot off its point.
      const element = document.createElement("div");
      element.dataset.place = pin.key;
      // A fixed box, so the marker's own anchor arithmetic cannot be thrown by the label hanging
      // outside it: the dot's centre is the coordinate, at every zoom.
      // No `relative` here: MapLibre positions the marker with `position: absolute`, and a utility class that
      // overrides it leaves every pin in the page flow, each one pushed down by the pins before it.
      element.className = "flex h-8 w-8 items-center justify-center";

      const color = CATEGORY_COLORS[pin.loc.cat];
      const dot = document.createElement("button");
      dot.type = "button";
      dot.dataset.dot = "";
      dot.className =
        "flex h-7 w-7 cursor-pointer items-center justify-center rounded-full border-2 border-white/90 text-[11px] font-bold text-slate-950 transition-transform hover:scale-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white";
      dot.style.backgroundColor = color;
      dot.style.boxShadow = glow(color);
      dot.textContent = pin.citations.length > 1 ? String(pin.citations.length) : "";
      const names = pin.citations.map((citation) => citation.title || citation.citation || "Authority").join("; ");
      const count = pin.citations.length === 1 ? "1 authority" : `${pin.citations.length} authorities`;
      dot.setAttribute("aria-label", `${count} at ${pin.label}: ${names}`);
      dot.title = `${pin.label}\n${names}`;
      dot.addEventListener("click", (event) => {
        event.stopPropagation();
        const members = groups.current.get(pin.key);
        if (members && members.length > 1) {
          // A pin standing for several places zooms in on them instead of opening one.
          const bounds = new maplibregl.LngLatBounds();
          for (const member of members) bounds.extend(member.lngLat);
          map.fitBounds(bounds, { padding: 120, maxZoom: 12, duration: reducedMotion() ? 0 : 900 });
          return;
        }
        onSelect({ key: pin.key, label: pin.label, citations: pin.citations });
      });

      const label = document.createElement("span");
      label.dataset.label = "";
      label.className =
        "pointer-events-none absolute left-1/2 top-full mt-1 -translate-x-1/2 whitespace-nowrap rounded-md border border-white/10 bg-slate-950/85 px-2 py-0.5 text-xs font-medium leading-tight text-slate-100 shadow-sm";
      label.textContent = shortLabel(pin.label);

      element.append(dot, label);
      const marker = new maplibregl.Marker({ element, anchor: "center" }).setLngLat(pin.lngLat).addTo(map);
      return { pin, marker };
    });

    declutter();
    fit();
  }, [ready, pins, edges, onSelect, fit, declutter]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.on("zoomend", declutter);
    map.on("moveend", declutter);
    return () => {
      map.off("zoomend", declutter);
      map.off("moveend", declutter);
    };
  }, [ready, declutter]);

  // The traversal: the places the tour has already walked, joined in order, inked over the dim links.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const pinOf = new Map(pins.map((pin) => [pin.key, pin] as const));
    const stops = trail.map((key) => pinOf.get(key)).filter((pin): pin is Pin => !!pin);
    const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
    for (let index = 1; index < stops.length; index += 1) {
      const from = stops[index - 1];
      const to = stops[index];
      if (from.key === to.key) continue;
      features.push({
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates: curve(from.lngLat, to.lngLat) },
      });
    }
    const data: GeoJSON.FeatureCollection<GeoJSON.LineString> = { type: "FeatureCollection", features };

    const source = map.getSource(TRAIL) as maplibregl.GeoJSONSource | undefined;
    if (source) {
      source.setData(data);
    } else {
      map.addSource(TRAIL, { type: "geojson", data });
      addArrow(map, CONTEXT_COLORS.trail);
      // A glow under the ink, so the walked path stays legible over county lines and names.
      map.addLayer({
        id: `${TRAIL}-casing`,
        type: "line",
        source: TRAIL,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": CONTEXT_COLORS.trailGlow, "line-width": 9, "line-blur": 5, "line-opacity": 0.55 },
      });
      map.addLayer({
        id: TRAIL,
        type: "line",
        source: TRAIL,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": CONTEXT_COLORS.trail, "line-width": 2.6 },
      });
      map.addLayer({
        id: `${TRAIL}-arrow`,
        type: "symbol",
        source: TRAIL,
        layout: {
          "symbol-placement": "line",
          "symbol-spacing": 48,
          "icon-image": ARROW,
          "icon-size": 0.7,
          "icon-rotation-alignment": "map",
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
      });
    }
    // While the walk is running the untouched links step back, so the traversal is the thing you see.
    const walking = features.length > 0;
    if (map.getLayer("links")) map.setPaintProperty("links", "line-opacity", walking ? 0.25 : 0.85);
    if (map.getLayer("links-glow")) map.setPaintProperty("links-glow", "line-opacity", walking ? 0.1 : 0.28);
  }, [ready, trail, pins]);

  // The tour marks the place it is speaking about, so the pin and the voice agree.
  useEffect(() => {
    lastFocus.current = focus;
    for (const { marker } of markers.current) {
      const element = marker.getElement();
      const dot = element.querySelector<HTMLElement>("[data-dot]");
      if (!dot) continue;
      const marked = focus !== null && element.dataset.place === focus;
      dot.classList.toggle("scale-125", marked);
      dot.classList.toggle("ring-4", marked);
      dot.classList.toggle("ring-white", marked);
      dot.classList.toggle("ring-offset-2", marked);
      dot.classList.toggle("ring-offset-slate-950", marked);
    }
    declutter();
  }, [focus, ready, pins, declutter]);

  // The camera follows the tour. The first stop starts from the whole country, then flies down to the
  // court; each stop after it flies straight to the next, rising over the distance and settling at the
  // scale of the place — a county for a Colorado court, a state for a federal one. When the walk ends
  // the camera levels out and every pin is back in view.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const was = lastFlightFocus.current;
    lastFlightFocus.current = focus;
    const pin = focus === null ? undefined : pins.find((candidate) => candidate.key === focus);
    if (!pin) {
      if (was !== null) {
        flight.current += 1;
        fit();
      }
      return;
    }
    const token = (flight.current += 1);
    const calm = reducedMotion();
    const go = () => {
      if (token !== flight.current) return;
      const options = {
        center: pin.lngLat,
        zoom: inColorado(pin) ? 9.2 : 6.3,
        pitch: calm ? 0 : TILT,
        bearing: 0,
      };
      if (calm) map.jumpTo(options);
      else map.flyTo({ ...options, speed: 0.85, curve: 1.5 });
    };
    if (was === null && !calm) {
      map.flyTo({ center: US_CENTER, zoom: US_ZOOM, pitch: 0, bearing: 0, duration: 1300 });
      map.once("moveend", go);
    } else {
      go();
    }
  }, [focus, ready, pins, fit]);

  // With nothing to place, the map rests on the whole country rather than on an arbitrary corner of it.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || pins.length) return;
    map.jumpTo({ center: US_CENTER, zoom: US_ZOOM, pitch: 0 });
  }, [ready, pins.length]);

  const toggleTilt = () => {
    const map = mapRef.current;
    if (!map) return;
    map.easeTo({ pitch: map.getPitch() > 8 ? 0 : TILT, duration: reducedMotion() ? 0 : 700 });
  };

  if (failed) {
    return (
      <div
        className={cn(
          "grid h-full place-items-center rounded-lg border border-border bg-muted p-6 text-center",
          className,
        )}
      >
        <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
          This browser did not give the page WebGL, so the map cannot be drawn. The authorities are still listed under
          Sources on the answer.
        </p>
      </div>
    );
  }

  const chip =
    "gap-1.5 border border-white/10 bg-slate-950/80 text-slate-100 shadow-sm backdrop-blur hover:bg-slate-900 hover:text-white";

  return (
    <div
      className={cn("relative h-full w-full overflow-hidden rounded-lg border border-white/10", className)}
      style={{ backgroundColor: GROUND.land }}
    >
      <div ref={container} className="absolute inset-0" />
      {/* A soft vignette, so the tiles sit in the card instead of bleeding out of it. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 shadow-[inset_0_0_80px_rgba(2,6,23,0.55)]"
      />

      <div className="absolute left-3 top-3 z-10 flex flex-wrap items-start gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={fit} className={chip}>
          <LocateFixed className="h-4 w-4" />
          Fit<span className="hidden sm:inline"> to the authorities</span>
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={toggleTilt}
          aria-pressed={tilted}
          className={cn(chip, tilted && "bg-slate-800 text-white")}
        >
          <Box className="h-4 w-4" />
          Tilt
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setKeyOpen((open) => !open)}
          aria-expanded={keyOpen}
          className={cn(chip, keyOpen && "bg-slate-800 text-white")}
        >
          <KeyRound className="h-4 w-4" />
          Key
        </Button>
      </div>

      {keyOpen && (
        <div className="absolute left-3 top-14 z-10 flex max-w-[18rem] flex-col gap-1.5 rounded-md border border-white/10 bg-slate-950/90 px-3 py-2 text-[11px] text-slate-300 shadow-lg backdrop-blur">
          <ul className="flex flex-wrap gap-x-3 gap-y-1">
            {(Object.keys(CATEGORY_LABELS) as (keyof typeof CATEGORY_LABELS)[]).map((category) => (
              <li key={category} className="flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: CATEGORY_COLORS[category], boxShadow: glow(CATEGORY_COLORS[category]) }}
                />
                {CATEGORY_LABELS[category]}
              </li>
            ))}
          </ul>
          <ul className="flex flex-wrap gap-x-3 gap-y-1 border-t border-white/10 pt-1.5">
            {(Object.keys(ARC_LABELS) as (keyof typeof ARC_LABELS)[]).map((arc) => (
              <li key={arc} className="flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="h-0.5 w-3 shrink-0 rounded-full"
                  style={{ backgroundColor: ARC_COLORS[arc] }}
                />
                {ARC_LABELS[arc]}
              </li>
            ))}
          </ul>
          {(county || trail.length > 1) && (
            <ul className="flex flex-wrap gap-x-3 gap-y-1 border-t border-white/10 pt-1.5">
              {county && (
                <li className="flex items-center gap-1.5">
                  <span
                    aria-hidden="true"
                    className="w-3 shrink-0 border-t border-dashed"
                    style={{ borderColor: CONTEXT_COLORS.county }}
                  />
                  County boundary
                </li>
              )}
              {trail.length > 1 && (
                <li className="flex items-center gap-1.5">
                  <span
                    aria-hidden="true"
                    className="h-0.5 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: CONTEXT_COLORS.trail }}
                  />
                  Path walked
                </li>
              )}
            </ul>
          )}
          <p className="border-t border-white/10 pt-1.5 text-slate-400">
            A numbered pin stands for several places that overlap at this zoom; click it to zoom in.
          </p>
        </div>
      )}

      {!pins.length && (
        <div className="pointer-events-none absolute inset-x-0 bottom-24 grid place-items-center p-6">
          <p className="rounded-md border border-white/10 bg-slate-950/85 px-3 py-2 text-sm text-slate-300 shadow-lg backdrop-blur">
            This answer cites no authority that can be placed on the map.
          </p>
        </div>
      )}
    </div>
  );
}
