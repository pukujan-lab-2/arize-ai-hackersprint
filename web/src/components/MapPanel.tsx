// Everything that used to float over the map in separate cards, as one panel with four tabs: the Tour
// (play, step, the caption), Places (every court on the map, and what was decided at the one you picked),
// Sources (the authorities and the opinion behind each) and Key. On a wide screen it is a sidebar beside
// the map, like a maps app; on a phone it is a sheet that pulls up from the bottom of the map.

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Layers, MapPin, Play, Square, Volume2, VolumeX, BookOpen, ArrowLeft } from "lucide-react";
import EvidenceList from "@/components/EvidenceList";
import { type MapPlace, shortLabel } from "@/components/CitationMap";
import MapKey from "@/components/MapKey";
import PullSheet from "@/components/PullSheet";
import SourcePane from "@/components/SourcePane";
import { Button } from "@/components/ui/button";
import type { NarrationStatus } from "@/hooks/use-narration";
import { citeType, courtName, locate, type Citation, type Safeguard } from "@/lib/citations";
import { nextTab, type SheetLevel } from "@/lib/sheetSwipe";
import type { TourStep } from "@/map/tour";
import { CATEGORY_COLORS } from "@/map/palette";
import { cn } from "@/lib/utils";

export type PanelTab = "tour" | "places" | "sources" | "key";
const TABS: readonly PanelTab[] = ["tour", "places", "sources", "key"];
const TAB_ICON = { tour: Play, places: MapPin, sources: BookOpen, key: Layers } as const;
const TAB_LABEL = { tour: "Tour", places: "Places", sources: "Sources", key: "Key" } as const;

export type PanelTour = {
  steps: TourStep[];
  index: number;
  status: NarrationStatus;
  heard: number;
  /** The place the camera is standing on, named the way its pin is. */
  at: string | null;
  /** Where the authorities came from, as the run recorded it. */
  path: string;
  start: () => void;
  stop: () => void;
  prev: () => void;
  next: () => void;
  canPrev: boolean;
  canNext: boolean;
};

type Props = {
  tour: PanelTour;
  places: MapPlace[];
  place: MapPlace | null;
  onPlace: (place: MapPlace | null) => void;
  citations: Citation[];
  answer: string;
  safeguard?: Safeguard;
  tab: PanelTab;
  onTab: (tab: PanelTab) => void;
  sourceIndex: number | null;
  onSourceIndex: (index: number | null) => void;
  onAsk: (question: string) => void;
};

function TourTab({ tour }: { tour: PanelTour }) {
  const active = tour.index >= 0;
  const current = active ? tour.steps[tour.index] : null;
  const text = current?.text ?? "";
  const seen = Math.min(Math.max(tour.heard, 0), text.length);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Button className="h-10 gap-2 roomy:h-11" onClick={active ? tour.stop : tour.start} disabled={!tour.steps.length}>
          {active ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {active ? "Stop" : "Play the tour"}
        </Button>
        <Button variant="outline" size="icon" className="h-10 w-10 roomy:h-11 roomy:w-11" onClick={tour.prev} disabled={!tour.canPrev} aria-label="Previous location" title="Previous location">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon" className="h-10 w-10 roomy:h-11 roomy:w-11" onClick={tour.next} disabled={!tour.canNext} aria-label={active ? "Next location" : "First location"} title={active ? "Next location" : "First location"}>
          <ChevronRight className="h-4 w-4" />
        </Button>
        <span className="ml-auto text-xs tabular-nums text-muted-foreground">
          {active ? `${tour.index + 1} of ${tour.steps.length}` : `${tour.steps.length} stops`}
        </span>
      </div>

      {active && current ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="rounded-full border border-border px-2 py-0.5 font-medium uppercase tracking-wide">{current.section}</span>
            {tour.at && (
              <span className="flex min-w-0 items-center gap-1">
                <MapPin className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{tour.at}</span>
              </span>
            )}
            <span className="ml-auto flex items-center gap-1">
              {tour.status === "unavailable" ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
              {tour.status === "loading" ? "Loading" : tour.status === "unavailable" ? "No voice" : tour.status === "speaking" ? "Speaking" : ""}
            </span>
          </div>
          <p className="text-base leading-relaxed">
            <span aria-hidden="true">
              {text.slice(0, seen)}
              <span className={cn(seen > 0 && "text-muted-foreground")}>{text.slice(seen)}</span>
            </span>
            <span className="sr-only" aria-live="polite">
              {current.section}: {text}
            </span>
          </p>
        </div>
      ) : (
        <p className="text-sm leading-relaxed text-muted-foreground">
          Speaks the answer, then flies to each authority where it sits. The arrows jump from court to court.
        </p>
      )}
      <p className="text-xs leading-relaxed text-muted-foreground">{tour.path}</p>
    </div>
  );
}

function PlacesTab({
  places,
  place,
  onPlace,
  onOpen,
}: {
  places: MapPlace[];
  place: MapPlace | null;
  onPlace: (place: MapPlace | null) => void;
  onOpen: (citation: Citation) => void;
}) {
  if (place) {
    return (
      <div className="space-y-3">
        <button
          type="button"
          onClick={() => onPlace(null)}
          className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          All places
        </button>
        <div>
          <h3 className="text-base font-semibold leading-snug">{place.label}</h3>
          <p className="text-xs text-muted-foreground">
            {place.citations.length} {place.citations.length === 1 ? "authority" : "authorities"} decided here
          </p>
        </div>
        <ul className="divide-y divide-border rounded-xl border border-border">
          {place.citations.map((citation, index) => (
            <li key={`${citation.id}-${index}`}>
              <button
                type="button"
                onClick={() => onOpen(citation)}
                className="w-full px-3 py-2.5 text-left transition-colors hover:bg-accent/50"
              >
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  {citation.ref && (
                    <span className="rounded bg-muted px-1.5 py-0.5 font-mono font-medium text-foreground">{citation.ref}</span>
                  )}
                  <span className="rounded bg-muted px-1.5 py-0.5 font-medium text-foreground">{citeType(citation)}</span>
                  <span className="truncate">{courtName(citation)}</span>
                </span>
                <span className="mt-1 line-clamp-2 block text-sm font-medium leading-snug">
                  {citation.title || citation.citation || "Authority"}
                </span>
                <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                  {[citation.citation, citation.date].filter(Boolean).join(" · ")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <ul className="divide-y divide-border rounded-xl border border-border">
      {places.map((item) => (
        <li key={item.key}>
          <button
            type="button"
            onClick={() => onPlace(item)}
            className="flex w-full items-center gap-3 px-3 py-3 text-left transition-colors hover:bg-accent/50"
          >
            <span
              aria-hidden="true"
              className="h-3 w-3 shrink-0 rounded-full"
              style={{ backgroundColor: CATEGORY_COLORS[locate(item.citations[0]).cat] }}
            />
            <span className="min-w-0 flex-1 text-sm font-medium">{shortLabel(item.label)}</span>
            <span className="text-xs tabular-nums text-muted-foreground">{item.citations.length}</span>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </button>
        </li>
      ))}
      {!places.length && <li className="px-3 py-4 text-sm text-muted-foreground">No authority could be placed on the map.</li>}
    </ul>
  );
}

export default function MapPanel({
  variant,
  onHeight,
  ...p
}: Props & { variant: "side" | "sheet"; onHeight?: (px: number) => void }) {
  const [level, setLevel] = useState<SheetLevel>(1);
  const detail = p.tab === "sources" && p.sourceIndex !== null;

  // Pulling the sheet to a tab, a place, an opinion or a tour stop opens it to at least the usual height.
  useEffect(() => {
    if (variant !== "sheet") return;
    if (p.sourceIndex !== null) setLevel(2); // an opinion is for reading: open it tall
    else if (p.place || p.tour.index >= 0) setLevel((current) => (current === 0 ? 1 : current));
  }, [variant, p.place, p.sourceIndex, p.tour.index]);

  const openCitation = (citation: Citation) => {
    const at = p.citations.findIndex((item) => item === citation || (!!item.id && item.id === citation.id));
    p.onSourceIndex(at >= 0 ? at : null);
    p.onTab("sources");
  };

  const tabsRow = (
    <div role="tablist" aria-label="Map panel" className="flex items-center gap-1 px-3 pb-2">
      {TABS.map((id) => {
        const Icon = TAB_ICON[id];
        const selected = p.tab === id;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-label={TAB_LABEL[id]}
            title={TAB_LABEL[id]}
            onClick={() => {
              if (id === "sources") p.onSourceIndex(null);
              p.onTab(id);
              if (variant === "sheet") setLevel((current) => (current === 0 ? 1 : current));
            }}
            className={cn(
              "flex h-11 flex-1 items-center justify-center gap-2 rounded-xl text-sm font-medium transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring motion-reduce:transition-none",
              selected ? "bg-secondary text-secondary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            <span className={cn(selected ? "inline" : "hidden", "sm:inline")}>{TAB_LABEL[id]}</span>
          </button>
        );
      })}
    </div>
  );

  const body = (
    <div key={`${p.tab}-${detail}`} className={cn(!detail && "animate-in fade-in slide-in-from-bottom-1 duration-200 motion-reduce:animate-none", detail && "h-full")}>
      {p.tab === "tour" && <TourTab tour={p.tour} />}
      {p.tab === "places" && <PlacesTab places={p.places} place={p.place} onPlace={p.onPlace} onOpen={openCitation} />}
      {p.tab === "sources" &&
        (detail ? (
          <SourcePane
            citations={p.citations}
            index={p.sourceIndex as number}
            answer={p.answer}
            safeguard={p.safeguard}
            onSelect={(index) => p.onSourceIndex(index)}
            onClose={() => p.onSourceIndex(null)}
            onAsk={p.onAsk}
            className="h-full"
          />
        ) : (
          <EvidenceList citations={p.citations} onOpen={openCitation} />
        ))}
      {p.tab === "key" && <MapKey />}
    </div>
  );

  if (variant === "side") {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <div className="shrink-0 pt-3">{tabsRow}</div>
        <div className={cn("min-h-0 flex-1", detail ? "overflow-hidden" : "overflow-y-auto px-4 pb-6 pt-1")}>{body}</div>
      </div>
    );
  }

  return (
    <PullSheet
      label="Map panel"
      level={level}
      onLevel={setLevel}
      onSide={(swipe) => p.onTab(nextTab(TABS, p.tab, swipe))}
      onHeight={onHeight}
      header={tabsRow}
      bare={detail}
    >
      {body}
    </PullSheet>
  );
}
