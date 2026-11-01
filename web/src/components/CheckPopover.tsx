// The shield on an answer, as something to press: it opens a short card saying what the citation check
// ran and what it found, in words, so the mark is never a mystery. The check tests references against
// the authorities the run retrieved; it does not test legal accuracy, and the card says so.

import { ShieldAlert, ShieldCheck } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Safeguard } from "@/lib/citations";
import { cn } from "@/lib/utils";

function Line({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span
        aria-hidden="true"
        className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", ok ? "bg-emerald-500" : "bg-destructive")}
      />
      <span>{children}</span>
    </li>
  );
}

export default function CheckPopover({ safeguard, citations }: { safeguard?: Safeguard; citations: number }) {
  const pass = safeguard?.pass;
  if (pass === undefined || pass === null) return null;
  const used = safeguard?.used?.length ?? 0;
  const invalid = safeguard?.invalid?.length ?? 0;
  const unknown = safeguard?.unknown_authorities?.length ?? 0;
  const unsupported = safeguard?.unsupported_claims?.length ?? 0;
  const Icon = pass ? ShieldCheck : ShieldAlert;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex h-9 w-9 items-center justify-center roomy:h-11 roomy:w-11 rounded-full border transition-colors hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring",
            pass
              ? "border-emerald-500/40 text-emerald-600 dark:text-emerald-400"
              : "border-destructive/50 text-destructive",
          )}
          aria-label={pass ? "Citations checked: see what was checked" : "Citation check failed: see what was found"}
        >
          <Icon className="h-4 w-4" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 space-y-2 text-sm">
        <p className="font-semibold">{pass ? "Citations checked" : "Citation check failed"}</p>
        <ul className="space-y-1.5 text-sm leading-snug">
          <Line ok={invalid === 0}>
            {used || citations} reference{(used || citations) === 1 ? "" : "s"} in the memo
            {invalid ? `, ${invalid} pointing at nothing` : " all point at a retrieved source"}.
          </Line>
          <Line ok={unknown === 0}>
            {unknown
              ? `${unknown} cited name${unknown === 1 ? " was" : "s were"} not in the retrieved set.`
              : "No case or statute appears that the retriever did not return."}
          </Line>
          <Line ok={unsupported === 0}>
            {unsupported
              ? `${unsupported} sentence${unsupported === 1 ? " has" : "s have"} no citation.`
              : "Every claim carries a citation."}
          </Line>
        </ul>
        <p className="border-t border-border pt-2 text-xs leading-relaxed text-muted-foreground">
          This checks references, not legal accuracy or whether the law is current. Open a source to read the passage.
        </p>
      </PopoverContent>
    </Popover>
  );
}
