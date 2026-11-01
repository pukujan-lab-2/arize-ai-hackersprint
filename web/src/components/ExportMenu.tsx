// Everything that takes a memo out of the page, in one menu: save it as a PDF, print it, share it, or
// open it in the reader's own mail app. Saving and printing use the browser's print dialog (a PDF is one
// of its destinations) over the report layout, so the file is real text, not a picture of the page.
// Nothing is sent anywhere by this app: email is a mail link, and sharing hands the text to the device.

import { FileDown, Link2, Mail, Printer, Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { RunResult } from "@/lib/citations";
import { mailtoHref, runLink, shareText } from "@/lib/export";
import { showError, showSuccess } from "@/utils/toast";

export default function ExportMenu({
  result,
  runId,
  onPrint,
}: {
  result: RunResult;
  runId: string;
  onPrint: () => void;
}) {
  const link = () => runLink(runId);

  const share = async () => {
    const text = shareText(result, link());
    try {
      if (navigator.share) {
        await navigator.share({ title: result.question || "Precedent memo", text, url: link() });
        return;
      }
      await navigator.clipboard.writeText(text);
      showSuccess("Memo summary copied. Paste it where you want to share it.");
    } catch (error) {
      // Closing the share sheet is not a failure.
      if ((error as Error)?.name !== "AbortError") showError("The browser would not share that");
    }
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(link());
      showSuccess("Link copied");
    } catch {
      showError("The browser would not copy that");
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 shrink-0 text-muted-foreground hover:text-foreground"
          aria-label="Export, print or share"
          title="Export, print or share"
        >
          <Share2 className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
          The memo, its opinions and their checks
        </DropdownMenuLabel>
        <DropdownMenuItem onSelect={onPrint} className="gap-2">
          <FileDown className="h-4 w-4" />
          Save as PDF
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onPrint} className="gap-2">
          <Printer className="h-4 w-4" />
          Print
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void share()} className="gap-2">
          <Share2 className="h-4 w-4" />
          Share
        </DropdownMenuItem>
        <DropdownMenuItem asChild className="gap-2">
          <a href={mailtoHref(result, link())}>
            <Mail className="h-4 w-4" />
            Email in your mail app
          </a>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void copyLink()} className="gap-2">
          <Link2 className="h-4 w-4" />
          Copy link
        </DropdownMenuItem>
        <p className="px-2 pb-1.5 pt-1 text-xs leading-snug text-muted-foreground">
          Email opens your own mail service with the summary written in; attach the PDF yourself. Nothing is sent from
          here.
        </p>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
