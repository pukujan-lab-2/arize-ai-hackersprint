// The tour's voice, written on the map like a subtitle: the line being spoken sits along the bottom of
// the map with the stop it is on, and the part already heard is bright while the rest is still dim, so
// the caption keeps pace with the voice. The arrows step between stops, so the walk can be taken at the
// reader's own pace. When the walk is idle the same strip offers the play button and says where the
// authorities came from — one strip, never a second panel under the map.

import { ChevronLeft, ChevronRight, MapPin, Play, Square, Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { NarrationStatus } from "@/hooks/use-narration";
import type { TourStep } from "@/map/tour";
import { cn } from "@/lib/utils";

export default function TourBar({
  steps,
  index,
  status,
  heard,
  at,
  path,
  onStart,
  onStop,
  onPrev,
  onNext,
  canPrev,
  canNext,
}: {
  steps: TourStep[];
  index: number;
  status: NarrationStatus;
  /** How much of the current line has been heard, in characters. */
  heard: number;
  /** The place the camera is standing on, named the way the pin is. Null on a stop about no place. */
  at: string | null;
  /** Where the authorities came from, as the run recorded it. */
  path: string;
  onStart: () => void;
  onStop: () => void;
  onPrev: () => void;
  onNext: () => void;
  /** Whether a place stands before / after this stop, so an arrow that would go nowhere is not offered. */
  canPrev: boolean;
  canNext: boolean;
}) {
  const active = index >= 0;
  const current = active ? steps[index] : null;
  const text = current?.text ?? "";
  const seen = Math.min(Math.max(heard, 0), text.length);

  // One card, centred along the bottom of the map and clear of the scale bar; the legend is a button
  // at the top, so nothing else competes for this edge.
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-9 z-10 px-3">
      <section
        aria-label="Tour"
        className="pointer-events-auto mx-auto w-full max-w-2xl rounded-xl border border-white/10 bg-slate-950/90 px-3 py-2 text-slate-100 shadow-2xl backdrop-blur"
      >
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Button size="sm" className="h-7 gap-1.5 px-2 text-xs" onClick={active ? onStop : onStart} disabled={!steps.length}>
            {active ? <Square className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
            {active ? "Stop" : "Play the tour"}
          </Button>

          {/* An arrow carries the camera, the caption and the voice to the next location, or back to the
              one before it. Prose stops sit nowhere, so the arrows pass over them. */}
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 border border-white/15 text-slate-100 hover:bg-white/10 hover:text-white"
              onClick={onPrev}
              disabled={!canPrev}
              aria-label="Previous location"
              title="Previous location"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 border border-white/15 text-slate-100 hover:bg-white/10 hover:text-white"
              onClick={onNext}
              disabled={!canNext}
              aria-label={active ? "Next location" : "First location"}
              title={active ? "Next location" : "First location"}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>

          <span className="text-xs tabular-nums text-slate-400">
            {active ? `${index + 1} of ${steps.length}` : `${steps.length} stops`}
          </span>

          {current && (
            <span className="rounded-full border border-white/15 px-1.5 py-0.5 text-xs font-medium uppercase tracking-wide text-slate-400">
              {current.section}
            </span>
          )}

          {/* The place the camera has just flown to, named as its pin is, so the two agree. */}
          {active && at && (
            <span className="flex min-w-0 items-center gap-1 text-xs text-slate-400">
              <MapPin className="h-3 w-3 shrink-0" />
              <span className="truncate">{at}</span>
            </span>
          )}

          <span className="ml-auto flex items-center gap-1.5 text-xs text-slate-400">
            {status === "unavailable" ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
            {status === "loading"
              ? "Audio loading…"
              : status === "unavailable"
                ? "Voice unavailable here"
                : status === "speaking"
                  ? "Speaking"
                  : active
                    ? ""
                    : "Speaks the answer, then each authority where it sits — the arrows jump court to court"}
          </span>
        </div>

        {/* The caption reads as a subtitle: the line, with the heard part bright and the rest to come. */}
        {active && current && (
          <p className="mt-1.5 max-h-24 overflow-hidden text-[13px] leading-relaxed text-slate-100">
            <span aria-hidden="true">
              {text.slice(0, seen)}
              <span className={cn(seen > 0 && "text-slate-400/70")}>{text.slice(seen)}</span>
            </span>
            <span className="sr-only" aria-live="polite">
              {current.section}: {text}
            </span>
          </p>
        )}

        {!active && <p className="mt-1 truncate text-xs text-slate-400">{path}</p>}
      </section>
    </div>
  );
}
