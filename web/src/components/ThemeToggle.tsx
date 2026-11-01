// Light, dark, or follow the system: one button that steps through the three, and says which it is on.
// The choice is remembered by next-themes; "system" is the default, so a first visit matches the device.

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

const ORDER = ["light", "dark", "system"] as const;
const LABEL = { light: "Light", dark: "Dark", system: "System" } as const;
const ICON = { light: Sun, dark: Moon, system: Monitor } as const;

export default function ThemeToggle({ className }: { className?: string }) {
  const { theme = "system", setTheme } = useTheme();
  // The stored theme is only known in the browser, so the first paint shows the neutral icon.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const current = (ORDER as readonly string[]).includes(theme) ? (theme as (typeof ORDER)[number]) : "system";
  const next = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length];
  const Icon = mounted ? ICON[current] : Monitor;

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={className}
      onClick={() => setTheme(next)}
      aria-label={`Theme: ${LABEL[current]}. Switch to ${LABEL[next]}`}
      title={`Theme: ${LABEL[current]} (click for ${LABEL[next]})`}
    >
      <Icon className="h-4 w-4" />
    </Button>
  );
}
