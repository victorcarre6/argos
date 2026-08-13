import { X } from "lucide-react";
import { useMemo, useState } from "react";

function SelectedFilters({
  values,
  onRemove,
}: {
  values: string[];
  onRemove: (value: string) => void;
}) {
  return values.map((value) => (
    <span
      key={value}
      className="inline-flex h-8 shrink-0 items-center gap-1 rounded-full border border-success/30 bg-success/15 px-2.5 text-xs font-medium text-success"
    >
      {value}
      <button
        type="button"
        onClick={() => onRemove(value)}
        className="rounded-full p-0.5 hover:bg-success/15"
        aria-label={`Retirer le filtre ${value}`}
      >
        <X className="size-3" />
      </button>
    </span>
  ));
}

export function SourceFilter({
  options,
  selected,
  onAdd,
  onRemove,
}: {
  options: string[];
  selected: string[];
  onAdd: (value: string) => void;
  onRemove: (value: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const suggestions = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("fr");
    if (!needle) return [];
    return options
      .filter(
        (option) =>
          !selected.includes(option) &&
          option.toLocaleLowerCase("fr").includes(needle),
      )
      .slice(0, 10);
  }, [options, query, selected]);

  const select = (value: string) => {
    onAdd(value);
    setQuery("");
    setOpen(false);
  };

  return (
    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
      <div className="relative min-w-64 flex-1">
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && suggestions[0]) {
              event.preventDefault();
              select(suggestions[0]);
            }
          }}
          placeholder="Toutes les sources"
          aria-label="Filtrer par source"
          aria-expanded={open && suggestions.length > 0}
          className="filter-text-field w-full rounded-md border border-border bg-background px-3 text-sm"
        />
        {open && suggestions.length > 0 && (
          <div className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-md border border-border bg-background p-1 shadow-lg">
            {suggestions.map((source) => (
              <button
                key={source}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => select(source)}
                className="block w-full rounded px-3 py-2 text-left text-sm hover:bg-muted"
              >
                {source}
              </button>
            ))}
          </div>
        )}
      </div>
      <SelectedFilters values={selected} onRemove={onRemove} />
    </div>
  );
}

export function TagFilter({
  options,
  selected,
  onAdd,
  onRemove,
  placeholder = "Tous les tags",
  ariaLabel = "Filtrer par tag",
}: {
  options: string[];
  selected: string[];
  onAdd: (value: string) => void;
  onRemove: (value: string) => void;
  placeholder?: string;
  ariaLabel?: string;
}) {
  return (
    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
      <select
        value=""
        onChange={(event) => event.target.value && onAdd(event.target.value)}
        aria-label={ariaLabel}
        className="h-9 min-w-48 rounded-md border border-border bg-background px-3 text-sm"
      >
        <option value="">{placeholder}</option>
        {options
          .filter((tag) => !selected.includes(tag))
          .map((tag) => (
            <option key={tag} value={tag}>
              {tag}
            </option>
          ))}
      </select>
      <SelectedFilters values={selected} onRemove={onRemove} />
    </div>
  );
}
