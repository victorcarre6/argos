import { ChevronDown, ChevronRight, Plus, Save } from "lucide-react";
import { useState } from "react";

import { Button, Card, SectionTitle } from "../components/ui";
import type { Category, Config, Priority, Source } from "../types";

const SOURCE_KEYS = [
  "recherche",
  "LLM",
  "IA Agentique",
  "Orchestration",
  "RAG",
  "Cloud",
  "HPC",
  "Deep Learning",
  "Ops",
  "Monitoring",
  "Politique",
  "Newsletter",
  "Cybersécurité",
  "Appels à projets",
];

const PRIORITY_BADGE: Record<Priority, string> = {
  1: "bg-red-500/15 text-red-600",
  2: "bg-emerald-500/15 text-emerald-600",
  3: "bg-muted text-muted-foreground",
};

const PRIORITY_BORDER: Record<Priority, string> = {
  1: "border-red-400/50",
  2: "border-emerald-400/40",
  3: "border-border",
};

function PriorityLabel({ priority }: { priority: Priority }) {
  return (
    <span
      className={`rounded px-2 py-0.5 font-mono text-xs font-semibold ${PRIORITY_BADGE[priority]}`}
    >
      P{priority}
    </span>
  );
}

function SourceEditor({
  source,
  update,
  remove,
}: {
  source: Source;
  update: (patch: Partial<Source>) => void;
  remove: () => void;
}) {
  const toggleKey = (key: string) =>
    update({
      keys: source.keys.includes(key)
        ? source.keys.filter((item) => item !== key)
        : [...source.keys, key],
    });

  return (
    <div
      className={`rounded-lg border bg-background p-3 ${PRIORITY_BORDER[source.priorité]}`}
    >
      <div className="grid gap-3 lg:grid-cols-[auto_minmax(190px,1fr)_minmax(280px,2fr)_90px_90px_auto] lg:items-end">
        <label className="flex h-9 items-center gap-2 text-xs font-medium">
          <input
            type="checkbox"
            checked={source.enabled !== false}
            onChange={(event) => update({ enabled: event.target.checked })}
            className="size-4"
          />
          <span>{source.enabled !== false ? "Active" : "Inactive"}</span>
        </label>
        <label className="text-xs font-medium text-muted-foreground">
          Source
          <input
            value={source.name}
            onChange={(event) => update({ name: event.target.value })}
            className="mt-1 h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          />
        </label>
        <label className="text-xs font-medium text-muted-foreground">
          Flux RSS/Atom
          <input
            value={source.url}
            onChange={(event) => update({ url: event.target.value })}
            className="mt-1 h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          />
        </label>
        <label className="text-xs font-medium text-muted-foreground">
          Priorité
          <select
            value={source.priorité}
            onChange={(event) =>
              update({ priorité: Number(event.target.value) as Priority })
            }
            className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
          >
            <option value={1}>P1</option>
            <option value={2}>P2</option>
            <option value={3}>P3</option>
          </select>
        </label>
        <label className="text-xs font-medium text-muted-foreground">
          Limite
          <input
            type="number"
            min={1}
            value={source.max_items ?? ""}
            onChange={(event) =>
              update({
                max_items: event.target.value
                  ? Number(event.target.value)
                  : undefined,
              })
            }
            placeholder="20"
            className="mt-1 h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          />
        </label>
        <Button variant="ghost" onClick={remove}>
          Retirer
        </Button>
      </div>
      <div className="mt-3 border-t border-border/60 pt-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">
            Clés de veille
          </span>
          <span className="text-xs text-muted-foreground">
            {source.keys.length} sélectionnée(s)
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {SOURCE_KEYS.map((key) => {
            const selected = source.keys.includes(key);
            return (
              <button
                type="button"
                key={key}
                onClick={() => toggleKey(key)}
                aria-pressed={selected}
                className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${selected ? "border-success/30 bg-success/15 text-success" : "border-border bg-muted/40 text-muted-foreground hover:bg-accent"}`}
              >
                {key}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CategorySummary({ category }: { category: Category }) {
  const active = category.sources.filter(
    (source) => source.enabled !== false,
  ).length;
  return (
    <>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{category.name}</span>
        <span className="block text-xs text-muted-foreground">
          {active}/{category.sources.length} actives
        </span>
      </span>
      <span className="hidden flex-wrap items-center gap-2 sm:flex">
        {([1, 2, 3] as Priority[]).map((priority) => (
          <span key={priority} className="inline-flex items-center gap-1">
            <PriorityLabel priority={priority} />
            <span className="text-xs text-muted-foreground">
              {
                category.sources.filter(
                  (source) => source.priorité === priority,
                ).length
              }
            </span>
          </span>
        ))}
      </span>
    </>
  );
}

export function SourcesView({
  config,
  onChange,
  onSave,
  saving,
}: {
  config: Config;
  onChange: (config: Config) => void;
  onSave: () => void;
  saving: boolean;
}) {
  const [openCategories, setOpenCategories] = useState<Set<number>>(new Set());
  const updateCategory = (index: number, patch: Partial<Category>) =>
    onChange({
      ...config,
      categories: config.categories.map((category, categoryIndex) =>
        categoryIndex === index ? { ...category, ...patch } : category,
      ),
    });
  const updateSource = (
    categoryIndex: number,
    sourceIndex: number,
    patch: Partial<Source>,
  ) => {
    const category = config.categories[categoryIndex];
    updateCategory(categoryIndex, {
      sources: category.sources.map((source, index) =>
        index === sourceIndex ? { ...source, ...patch } : source,
      ),
    });
  };
  const toggleCategory = (index: number) =>
    setOpenCategories((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  const totalSources = config.categories.reduce(
    (total, category) => total + category.sources.length,
    0,
  );
  const activeSources = config.categories.reduce(
    (total, category) =>
      total +
      category.sources.filter((source) => source.enabled !== false).length,
    0,
  );

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <SectionTitle>Sources de veille</SectionTitle>
            <p className="text-sm text-muted-foreground">
              {config.categories.length} catégories · {activeSources}/
              {totalSources} sources actives · {Object.keys(config.tags).length}{" "}
              tags
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="ghost"
              onClick={() =>
                setOpenCategories(
                  new Set(config.categories.map((_, index) => index)),
                )
              }
            >
              Tout déplier
            </Button>
            <Button
              variant="ghost"
              onClick={() => setOpenCategories(new Set())}
            >
              Tout replier
            </Button>
            <Button
              onClick={onSave}
              disabled={saving}
              iconStart={<Save className="size-4" />}
            >
              {saving ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </div>
        </div>
      </Card>

      {config.categories.map((category, categoryIndex) => {
        const open = openCategories.has(categoryIndex);
        return (
          <Card
            key={`${category.name}-${categoryIndex}`}
            className="overflow-hidden"
          >
            <button
              type="button"
              onClick={() => toggleCategory(categoryIndex)}
              aria-expanded={open}
              className="flex w-full items-center gap-3 px-4 py-4 text-left hover:bg-muted/60"
            >
              {open ? (
                <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
              ) : (
                <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
              )}
              <span
                className="size-3 shrink-0 rounded-full"
                style={{ backgroundColor: category.color ?? "#6d5dfc" }}
              />
              <CategorySummary category={category} />
            </button>
            {open && (
              <div className="border-t border-border bg-muted/20 p-4">
                <div className="grid gap-3 rounded-lg border border-border bg-background p-3 md:grid-cols-[80px_minmax(220px,1fr)]">
                  <label className="text-xs font-medium text-muted-foreground">
                    Couleur
                    <input
                      type="color"
                      value={category.color ?? "#6d5dfc"}
                      onChange={(event) =>
                        updateCategory(categoryIndex, {
                          color: event.target.value,
                        })
                      }
                      className="mt-1 block h-9 w-full cursor-pointer rounded border border-border bg-background p-1"
                    />
                  </label>
                  <label className="text-xs font-medium text-muted-foreground">
                    Nom de la catégorie
                    <input
                      value={category.name}
                      onChange={(event) =>
                        updateCategory(categoryIndex, {
                          name: event.target.value,
                        })
                      }
                      className="mt-1 h-9 w-full rounded-md border border-border bg-background px-3 text-sm font-medium"
                    />
                  </label>
                </div>
                <div className="mt-4 space-y-3">
                  {category.sources.map((source, sourceIndex) => (
                    <SourceEditor
                      key={`${source.name}-${sourceIndex}`}
                      source={source}
                      update={(patch) =>
                        updateSource(categoryIndex, sourceIndex, patch)
                      }
                      remove={() =>
                        updateCategory(categoryIndex, {
                          sources: category.sources.filter(
                            (_, index) => index !== sourceIndex,
                          ),
                        })
                      }
                    />
                  ))}
                </div>
                <Button
                  variant="secondary"
                  className="mt-4"
                  iconStart={<Plus className="size-4" />}
                  onClick={() =>
                    updateCategory(categoryIndex, {
                      sources: [
                        ...category.sources,
                        {
                          name: "Nouvelle source",
                          url: "https://",
                          keys: ["recherche"],
                          priorité: 3,
                        },
                      ],
                    })
                  }
                >
                  Ajouter une source
                </Button>
              </div>
            )}
          </Card>
        );
      })}
      <Button
        variant="secondary"
        iconStart={<Plus className="size-4" />}
        onClick={() => {
          const index = config.categories.length;
          onChange({
            ...config,
            categories: [
              ...config.categories,
              {
                name: "Nouvelle catégorie",
                color: "#6d5dfc",
                sources: [],
              },
            ],
          });
          setOpenCategories((current) => new Set([...current, index]));
        }}
      >
        Ajouter une catégorie
      </Button>
    </div>
  );
}
