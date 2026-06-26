import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
} from "react";

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

type ButtonVariant = "primary" | "secondary" | "ghost";

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
}) {
  return (
    <button
      className={cn("ds-button", `ds-button-${variant}`, className)}
      {...props}
    />
  );
}

export function Card({
  className,
  hover = true,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  hover?: boolean;
}) {
  return (
    <div
      className={cn("ds-card", className)}
      data-hover={hover ? "true" : "false"}
      {...props}
    />
  );
}

export function GradientBorderCard({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
}) {
  return (
    <div className={cn("ds-card ds-gradient-border", className)} {...props}>
      <div className="ds-gradient-border-inner">{children}</div>
    </div>
  );
}

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("ds-input", className)} {...props} />;
}

export function SectionLabel({
  children,
  pulse = false,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  pulse?: boolean;
}) {
  return (
    <div
      className={cn("ds-section-label", className)}
      data-pulse={pulse ? "true" : "false"}
      {...props}
    >
      {children}
    </div>
  );
}
