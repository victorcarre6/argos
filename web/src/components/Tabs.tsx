import * as RadixTabs from "@radix-ui/react-tabs";
import cn from "classnames";

export interface TabItem<T extends string = string> {
  value: T;
  label: string;
  disabled?: boolean;
}

type TabTheme = "pill" | "underline";

const THEMES: Record<TabTheme, { list: string; trigger: string }> = {
  pill: {
    list: "inline-flex h-9 gap-1 rounded-lg bg-secondary p-1",
    trigger:
      "rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm",
  },
  underline: {
    list: "flex h-9 gap-1 border-b border-border",
    trigger:
      "-mb-px border-b-2 border-transparent px-3 text-sm font-medium text-muted-foreground transition-colors data-[state=active]:border-foreground data-[state=active]:text-foreground",
  },
};

/**
 * Controlled tab bar (renders only the triggers — you render the panels).
 *
 *   <Tabs value={tab} onValueChange={setTab} items={items} />
 *   {tab === "a" && <PanelA />}
 */
export function Tabs<T extends string = string>({
  items,
  value,
  onValueChange,
  theme = "pill",
  className,
}: {
  items: TabItem<T>[];
  value: T;
  onValueChange: (value: T) => void;
  theme?: TabTheme;
  className?: string;
}) {
  const t = THEMES[theme];
  return (
    <RadixTabs.Root
      className={className}
      value={value}
      onValueChange={(v) => onValueChange(v as T)}
    >
      <RadixTabs.List className={t.list}>
        {items.map((item) => (
          <RadixTabs.Trigger
            key={item.value}
            value={item.value}
            disabled={item.disabled}
            className={cn(
              "disabled:cursor-not-allowed disabled:opacity-50",
              t.trigger,
            )}
          >
            {item.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
    </RadixTabs.Root>
  );
}
