// Shown under an answer that came from the backup search because the full engine was asleep. It watches the
// engine load and, once it is up, offers the full search: the same question asked again.

import { useEffect, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  question: string;
  /** Only the newest answer polls; older ones just show the words. */
  watch: boolean;
  onRun: (question: string) => void;
};

/** The engine's own status as /api/health reports it: "ready", "waking", "asleep"... */
async function engineStatus(): Promise<string | null> {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    if (!response.ok) return null;
    const body = (await response.json()) as { engine?: { ok?: boolean; status?: string } };
    return body.engine?.ok ? "ready" : body.engine?.status || null;
  } catch {
    return null;
  }
}

export default function QuickAnswerNotice({ question, watch, onRun }: Props) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!watch || ready) return;
    let live = true;
    const check = () =>
      void engineStatus().then((status) => {
        if (live && status === "ready") setReady(true);
      });
    check();
    const timer = window.setInterval(check, 5000);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, [watch, ready]);

  return (
    <div role="status" className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
      <p>
        Quick answer from the backup search. The full search engine was asleep
        {watch && !ready ? " and is loading, which takes about a minute or two." : "."}
      </p>
      {watch && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-9 gap-1.5 roomy:h-11"
          disabled={!ready}
          onClick={() => onRun(question)}
        >
          {ready ? <Search className="h-3.5 w-3.5" /> : <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {ready ? "Run the full search" : "Loading the full search"}
        </Button>
      )}
    </div>
  );
}
