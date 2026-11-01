// What an empty chat offers: a few easy questions to start from, a row of subjects to switch between,
// and a shuffle for more. Nothing here is the same twice in a row, so every new chat starts differently.

import { useMemo, useState } from "react";
import { ArrowUpRight, Shuffle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { QUESTION_GROUPS, groupQuestions, popularQuestions } from "@/lib/questions";
import { cn } from "@/lib/utils";

export default function QuestionBank({ onAsk }: { onAsk: (question: string) => void }) {
  const [group, setGroup] = useState("popular");
  const [round, setRound] = useState(0);
  // The cards change with the subject and with every shuffle, and are chosen once per change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const questions = useMemo(() => (group === "popular" ? popularQuestions(4) : groupQuestions(group, 4)), [group, round]);

  return (
    <div>
      <div className="flex items-center gap-2">
        <div
          role="tablist"
          aria-label="Question subjects"
          className="-mx-1 flex min-w-0 flex-1 gap-1.5 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {[{ id: "popular", label: "Popular" }, ...QUESTION_GROUPS].map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={group === item.id}
              onClick={() => setGroup(item.id)}
              className={cn(
                "shrink-0 rounded-full border px-3.5 py-1.5 text-sm transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring motion-reduce:transition-none",
                group === item.id
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-9 w-9 shrink-0 text-muted-foreground hover:text-foreground"
          onClick={() => setRound((value) => value + 1)}
          aria-label="Show different questions"
          title="Show different questions"
        >
          <Shuffle className="h-4 w-4" />
        </Button>
      </div>

      <ul key={`${group}-${round}`} className="mt-3 grid gap-2.5 sm:grid-cols-2">
        {questions.map((question, index) => (
          <li
            key={question}
            className="animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-300 motion-reduce:animate-none"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <button
              type="button"
              onClick={() => onAsk(question)}
              className="group flex h-full w-full items-start justify-between gap-3 rounded-2xl border border-border bg-card px-4 py-3.5 text-left text-[15px] leading-snug transition-all duration-200 hover:border-foreground/25 hover:bg-accent/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring motion-reduce:transition-none"
            >
              <span className="min-w-0">{question}</span>
              <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-foreground motion-reduce:transition-none" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
