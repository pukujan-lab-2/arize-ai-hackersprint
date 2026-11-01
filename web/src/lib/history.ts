// Which saved chats this device has archived or removed. The server keeps every run and has no way to
// delete one, and the list it returns is already this device's own, so archiving and removing are
// remembered here, in the browser: a removed chat disappears from this device's list and nowhere else.

import { useCallback, useEffect, useState } from "react";

const ARCHIVED = "precedent.archived";
const REMOVED = "precedent.removed";

function read(key: string): string[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(key) || "[]");
    return Array.isArray(raw) ? raw.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function write(key: string, ids: string[]) {
  try {
    window.localStorage.setItem(key, JSON.stringify(ids));
  } catch {
    // Storage can be blocked; the change still holds for this visit.
  }
}

export function useChatShelf() {
  const [archived, setArchived] = useState<string[]>(() => read(ARCHIVED));
  const [removed, setRemoved] = useState<string[]>(() => read(REMOVED));

  useEffect(() => write(ARCHIVED, archived), [archived]);
  useEffect(() => write(REMOVED, removed), [removed]);

  const archive = useCallback((id: string) => setArchived((list) => (list.includes(id) ? list : [...list, id])), []);
  const unarchive = useCallback((id: string) => setArchived((list) => list.filter((item) => item !== id)), []);
  const remove = useCallback((id: string) => setRemoved((list) => (list.includes(id) ? list : [...list, id])), []);
  const restore = useCallback((id: string) => setRemoved((list) => list.filter((item) => item !== id)), []);

  return { archived, removed, archive, unarchive, remove, restore };
}
