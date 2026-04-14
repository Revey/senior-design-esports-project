"use client";

import { useEffect, useRef, useState } from "react";

type Props<T> = {
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  fetcher: (q: string) => Promise<T[]>;
  render: (item: T) => string;
  onSelect: (item: T) => void;
  onCreate?: (q: string) => Promise<T>;
  createLabel?: (q: string) => string;
};

export default function Typeahead<T>({
  placeholder,
  value,
  onChange,
  fetcher,
  render,
  onSelect,
  onCreate,
  createLabel,
}: Props<T>) {
  const [items, setItems] = useState<T[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (!value) {
      setItems([]);
      return;
    }
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        setItems(await fetcher(value));
      } finally {
        setLoading(false);
      }
    }, 180);
  }, [value, fetcher]);

  return (
    <div className="relative">
      <input
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded bg-black/40 border border-white/20 outline-none focus:border-white/50"
      />
      {open && (value || loading) && (
        <div className="absolute z-20 mt-1 w-full max-h-60 overflow-auto rounded border border-white/15 bg-neutral-900 shadow-lg">
          {loading && <div className="px-3 py-2 text-sm text-white/50">Searching…</div>}
          {!loading &&
            items.map((it, i) => (
              <button
                key={i}
                type="button"
                className="block w-full text-left px-3 py-2 text-sm hover:bg-white/10"
                onClick={() => {
                  onSelect(it);
                  setOpen(false);
                }}
              >
                {render(it)}
              </button>
            ))}
          {!loading && items.length === 0 && onCreate && value.trim() && (
            <button
              type="button"
              className="block w-full text-left px-3 py-2 text-sm hover:bg-white/10 text-emerald-400"
              onClick={async () => {
                const created = await onCreate(value.trim());
                onSelect(created);
                setOpen(false);
              }}
            >
              {createLabel ? createLabel(value) : `+ Create "${value}"`}
            </button>
          )}
          {!loading && items.length === 0 && !onCreate && (
            <div className="px-3 py-2 text-sm text-white/50">No results</div>
          )}
        </div>
      )}
    </div>
  );
}
