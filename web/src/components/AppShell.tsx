// The frame: the conversation history on the left, the one page on the right. History is the runs this
// device asked for; a saved run opens at `/?run=<id>`, so a conversation can be linked to and reloaded.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Outlet, useNavigate, useSearchParams } from "react-router-dom";
import { Archive, ArchiveRestore, ChevronDown, MessageSquarePlus, MessagesSquare, MoreHorizontal, Trash2 } from "lucide-react";
import { toast } from "sonner";
import ThemeToggle from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { loadRuns, type Source } from "@/lib/api";
import { useChatShelf } from "@/lib/history";
import { isToday, whenLabel, withinDays, type SavedRun } from "@/lib/runs";
import { cn } from "@/lib/utils";

/** What the page under the shell reads: the history, where it came from, and how to start over. */
export type ShellContext = {
  runs: SavedRun[];
  source: Source | "loading";
  refreshRuns: () => void;
  /** Bumped every time the reader asks for a new conversation. */
  resetToken: number;
  /** Opens the conversation list below the wide breakpoint. */
  openNav: () => void;
};

function Brand() {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <img src="/logo.svg" alt="" aria-hidden="true" className="h-8 w-8 shrink-0" />
      <span className="min-w-0">
        <span className="block text-sm font-semibold leading-tight tracking-tight">Precedent</span>
      </span>
    </div>
  );
}

type Group = { title: string; runs: SavedRun[] };

function groupRuns(runs: SavedRun[]): Group[] {
  const today: SavedRun[] = [];
  const week: SavedRun[] = [];
  const earlier: SavedRun[] = [];
  for (const run of runs) {
    if (isToday(run.ts)) today.push(run);
    else if (withinDays(run.ts, 7)) week.push(run);
    else earlier.push(run);
  }
  return [
    { title: "Today", runs: today },
    { title: "Previous 7 days", runs: week },
    { title: "Earlier", runs: earlier },
  ].filter((group) => group.runs.length > 0);
}

function History({
  runs,
  activeRun,
  onOpen,
  onArchive,
  onDelete,
  archived = false,
}: {
  runs: SavedRun[];
  activeRun: string;
  onOpen: (runId: string) => void;
  onArchive: (runId: string) => void;
  onDelete: (runId: string) => void;
  /** In the Archived list the archive action reads "Unarchive". */
  archived?: boolean;
}) {
  const groups = useMemo(() => (archived ? [{ title: "", runs }] : groupRuns(runs)), [runs, archived]);

  if (!groups.length || !groups[0].runs.length) {
    return archived ? null : (
      <p className="px-2 py-3 text-xs leading-relaxed text-muted-foreground">Your questions appear here.</p>
    );
  }

  return (
    <div className="space-y-3">
      {groups.map((group) => (
        <section key={group.title || "all"}>
          {group.title && (
            <h2 className="px-2 pb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {group.title}
            </h2>
          )}
          <ul className="space-y-0.5">
            {group.runs.map((run) => (
              <li key={run.run_id} className="group relative">
                <button
                  type="button"
                  onClick={() => onOpen(run.run_id)}
                  aria-current={run.run_id === activeRun ? "true" : undefined}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-md py-2 pl-2 pr-10 text-left transition-colors",
                    run.run_id === activeRun
                      ? "bg-secondary text-secondary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  <MessagesSquare className="mt-0.5 h-4 w-4 shrink-0" />
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 block text-sm leading-snug">{run.question}</span>
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">{whenLabel(run.ts)}</span>
                  </span>
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute right-0 top-0.5 h-10 w-10 text-muted-foreground sm:right-1 sm:top-1.5 sm:h-7 sm:w-7 opacity-100 transition-opacity hover:text-foreground focus-visible:opacity-100 data-[state=open]:opacity-100 lg:opacity-0 lg:group-hover:opacity-100"
                      aria-label={`Options for: ${run.question}`}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-52">
                    <DropdownMenuItem onSelect={() => onArchive(run.run_id)} className="gap-2">
                      {archived ? <ArchiveRestore className="h-4 w-4" /> : <Archive className="h-4 w-4" />}
                      {archived ? "Unarchive" : "Archive"}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onSelect={() => onDelete(run.run_id)}
                      className="gap-2 text-destructive focus:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                      Delete from this device
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

export default function AppShell() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const activeRun = (params.get("run") || "").trim();

  const [runs, setRuns] = useState<SavedRun[]>([]);
  const shelf = useChatShelf();
  const [showArchived, setShowArchived] = useState(false);
  const [source, setSource] = useState<Source | "loading">("loading");
  const [resetToken, setResetToken] = useState(0);
  const [navOpen, setNavOpen] = useState(false);

  const refreshRuns = useCallback(() => {
    void loadRuns().then(({ runs: list, source: where }) => {
      setRuns(list);
      setSource(where);
    });
  }, []);

  useEffect(() => {
    refreshRuns();
  }, [refreshRuns]);

  const newChat = () => {
    setNavOpen(false);
    setResetToken((token) => token + 1);
    navigate("/");
  };

  const openRun = (runId: string) => {
    setNavOpen(false);
    navigate(`/?run=${encodeURIComponent(runId)}`);
  };

  const archivedRuns = runs.filter((run) => shelf.archived.includes(run.run_id) && !shelf.removed.includes(run.run_id));

  const archiveChat = (runId: string) => {
    shelf.archive(runId);
    toast("Chat archived", { action: { label: "Undo", onClick: () => shelf.unarchive(runId) } });
    if (runId === activeRun) navigate("/");
  };

  const deleteChat = (runId: string) => {
    shelf.remove(runId);
    toast("Chat deleted from this device", { action: { label: "Undo", onClick: () => shelf.restore(runId) } });
    if (runId === activeRun) navigate("/");
  };

  const sidebar = (onNavigate?: () => void) => (
    <>
      <div className="px-3 py-3">
        <Brand />
      </div>
      <div className="px-3">
        <Button className="h-11 w-full justify-start gap-2 sm:h-9" size="sm" onClick={newChat}>
          <MessageSquarePlus className="h-4 w-4" />
          New chat
        </Button>
      </div>
      <nav aria-label="Conversations" className="mt-3 min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        <History
          runs={runs.filter((run) => !shelf.removed.includes(run.run_id) && !shelf.archived.includes(run.run_id))}
          activeRun={activeRun}
          onOpen={(runId) => {
            onNavigate?.();
            openRun(runId);
          }}
          onArchive={archiveChat}
          onDelete={deleteChat}
        />
        {archivedRuns.length > 0 && (
          <div className="mt-3 border-t border-border pt-2">
            <button
              type="button"
              onClick={() => setShowArchived((open) => !open)}
              aria-expanded={showArchived}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground"
            >
              <Archive className="h-3.5 w-3.5" />
              <span className="flex-1">Archived ({archivedRuns.length})</span>
              <ChevronDown
                className={cn("h-4 w-4 transition-transform duration-200 motion-reduce:transition-none", showArchived && "rotate-180")}
              />
            </button>
            {showArchived && (
              <div className="mt-1 animate-in fade-in slide-in-from-top-1 duration-200 motion-reduce:animate-none">
                <History
                  archived
                  runs={archivedRuns}
                  activeRun={activeRun}
                  onOpen={(runId) => {
                    onNavigate?.();
                    openRun(runId);
                  }}
                  onArchive={(runId) => shelf.unarchive(runId)}
                  onDelete={deleteChat}
                />
              </div>
            )}
          </div>
        )}
      </nav>
      <div className="border-t border-border p-2">
        <ThemeToggle withLabel className="w-full justify-start gap-2.5 px-2.5 text-muted-foreground hover:text-foreground" />
      </div>
    </>
  );

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-background text-foreground">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card/60 lg:flex">{sidebar()}</aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1">
          <Outlet context={{ runs, source, refreshRuns, resetToken, openNav: () => setNavOpen(true) } satisfies ShellContext} />
        </div>
      </div>

      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left" className="flex w-72 flex-col bg-card p-0">
          <SheetTitle className="sr-only">Conversations</SheetTitle>
          {sidebar(() => setNavOpen(false))}
        </SheetContent>
      </Sheet>
    </div>
  );
}
