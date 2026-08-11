import cn from "classnames";
import type { ButtonHTMLAttributes, ReactNode } from "react";

/* --------------------------------------------------------------------------
 * Button
 * ------------------------------------------------------------------------ */

type ButtonVariant = "primary" | "secondary" | "success" | "ghost";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-brand text-brand-foreground hover:opacity-90",
  secondary:
    "bg-secondary text-secondary-foreground hover:bg-accent border border-border",
  success: "bg-success text-white hover:opacity-90",
  ghost: "bg-transparent text-foreground hover:bg-muted",
};

export const Button = ({
  variant = "primary",
  iconStart,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  iconStart?: ReactNode;
}) => (
  <button
    className={cn(
      "inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
      BUTTON_VARIANT[variant],
      className,
    )}
    {...rest}
  >
    {iconStart}
    {children}
  </button>
);

/* --------------------------------------------------------------------------
 * Surfaces & text
 * ------------------------------------------------------------------------ */

/** Rounded, bordered surface — the base of every panel/card. */
export const Card = ({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) => (
  <div
    className={cn(
      "rounded-xl border border-border bg-background shadow-sm",
      className,
    )}
  >
    {children}
  </div>
);

export const SectionTitle = ({ children }: { children: ReactNode }) => (
  <h3 className="mb-3 text-sm font-semibold text-foreground">{children}</h3>
);

export function TabBar<T extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: ReadonlyArray<{ value: T; label: string; icon?: ReactNode }>;
  value: T;
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex w-fit max-w-full gap-1 overflow-x-auto rounded-lg bg-secondary p-1",
        className,
      )}
    >
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          onClick={() => onChange(item.value)}
          className={cn(
            "flex h-8 shrink-0 items-center gap-2 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
            value === item.value &&
              "bg-background text-foreground shadow-sm hover:text-foreground",
          )}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </div>
  );
}

/** Tiny uppercase caption. */
export const Label = ({ children }: { children: ReactNode }) => (
  <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-secondary-foreground">
    {children}
  </div>
);

/* --------------------------------------------------------------------------
 * Pill
 * ------------------------------------------------------------------------ */

type Tone = "neutral" | "brand" | "success" | "error" | "warning";

const PILL_TONE: Record<Tone, string> = {
  neutral: "bg-secondary text-secondary-foreground",
  brand: "bg-brand/12 text-brand",
  success: "bg-success/15 text-success",
  error: "bg-error/15 text-error",
  warning: "bg-warning/15 text-warning",
};

export const Pill = ({
  tone = "neutral",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) => (
  <span
    className={cn(
      "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
      PILL_TONE[tone],
    )}
  >
    {children}
  </span>
);

/* --------------------------------------------------------------------------
 * Misc
 * ------------------------------------------------------------------------ */

/** Empty / placeholder state. */
export const Empty = ({ children }: { children: ReactNode }) => (
  <div className="rounded-lg border border-dashed border-border bg-muted px-4 py-8 text-center text-sm text-muted-foreground">
    {children}
  </div>
);
