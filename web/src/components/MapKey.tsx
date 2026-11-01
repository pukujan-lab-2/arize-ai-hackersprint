// What the colours and lines on the map mean, as the Key tab shows them.

import { ARC_COLORS, ARC_LABELS, CATEGORY_COLORS, CATEGORY_LABELS, CONTEXT_COLORS } from "@/map/palette";

const glow = (color: string) => `0 0 0 3px ${color}33, 0 0 10px 1px ${color}88`;

export default function MapKey() {
  return (
    <div className="space-y-4 text-sm">
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Pins</h3>
        <ul className="mt-2 space-y-2">
          {(Object.keys(CATEGORY_LABELS) as (keyof typeof CATEGORY_LABELS)[]).map((category) => (
            <li key={category} className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className="h-3 w-3 shrink-0 rounded-full"
                style={{ backgroundColor: CATEGORY_COLORS[category], boxShadow: glow(CATEGORY_COLORS[category]) }}
              />
              {CATEGORY_LABELS[category]}
            </li>
          ))}
          <li className="flex items-center gap-3 text-muted-foreground">
            <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-slate-300 text-xs font-bold text-slate-950">
              3
            </span>
            Several places that overlap at this zoom; tap to zoom in
          </li>
        </ul>
      </section>
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Links</h3>
        <ul className="mt-2 space-y-2">
          {(Object.keys(ARC_LABELS) as (keyof typeof ARC_LABELS)[]).map((arc) => (
            <li key={arc} className="flex items-center gap-3">
              <span aria-hidden="true" className="h-0.5 w-5 shrink-0 rounded-full" style={{ backgroundColor: ARC_COLORS[arc] }} />
              {ARC_LABELS[arc]}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Ground</h3>
        <ul className="mt-2 space-y-2">
          <li className="flex items-center gap-3">
            <span aria-hidden="true" className="w-5 shrink-0 border-t border-dashed" style={{ borderColor: CONTEXT_COLORS.county }} />
            County boundary
          </li>
          <li className="flex items-center gap-3">
            <span aria-hidden="true" className="h-0.5 w-5 shrink-0 rounded-full" style={{ backgroundColor: CONTEXT_COLORS.trail }} />
            Path the tour has walked
          </li>
        </ul>
      </section>
    </div>
  );
}
