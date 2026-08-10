import cn from "classnames";
import { ChevronDown } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

/* --------------------------------------------------------------------------
 * Button
 * ------------------------------------------------------------------------ */

type ButtonVariant = "primary" | "secondary" | "ghost";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-brand text-brand-foreground hover:opacity-90",
  secondary:
    "bg-secondary text-secondary-foreground hover:bg-accent border border-border",
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

/** Tiny uppercase caption. */
export const Label = ({ children }: { children: ReactNode }) => (
  <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-secondary-foreground">
    {children}
  </div>
);

/* --------------------------------------------------------------------------
 * Pill / Field
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

/** `[pill label] ……… value` row — the canonical key/value line. */
export const Field = ({
  label,
  value,
}: {
  label: ReactNode;
  value: unknown;
}) => (
  <div className="flex items-center justify-between gap-3">
    <Pill tone="brand">{label}</Pill>
    <span
      className="truncate font-mono text-sm text-foreground"
      title={String(value)}
    >
      {String(value)}
    </span>
  </div>
);

/** Plain key/value line (no pill). */
export const KV = ({ label, value }: { label: ReactNode; value: unknown }) => (
  <div className="flex items-baseline justify-between gap-4 border-b border-border/50 py-1.5 last:border-0">
    <span className="text-xs font-medium text-secondary-foreground">
      {label}
    </span>
    <span className="truncate text-right text-sm text-foreground">
      {String(value)}
    </span>
  </div>
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

/** Collapsible section with an animated chevron. */
export const Expander = ({
  label,
  open,
  children,
}: {
  label: string;
  open?: boolean;
  children: ReactNode;
}) => (
  <details
    open={open}
    className="group my-1 overflow-hidden rounded-lg border border-border"
  >
    <summary className="flex cursor-pointer select-none items-center justify-between px-3 py-2 text-sm text-muted-foreground hover:bg-muted">
      <span>{label}</span>
      <ChevronDown className="size-4 transition-transform group-open:rotate-180" />
    </summary>
    <div className="border-t border-border px-3 py-2">{children}</div>
  </details>
);

/** Monospaced preformatted block. */
export const Code = ({ children }: { children: ReactNode }) => (
  <pre className="overflow-auto rounded-lg bg-muted p-3 text-xs leading-relaxed text-foreground">
    {children}
  </pre>
);
