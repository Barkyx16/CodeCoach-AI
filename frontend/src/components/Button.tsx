import type { ButtonHTMLAttributes, ReactNode } from "react";

import { Spinner } from "./Spinner";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  loading?: boolean;
  icon?: ReactNode;
}

/**
 * While `loading`, the button ignores presses but stays focusable (aria-disabled, not the
 * `disabled` attribute): browsers drop focus from a disabled button, which would throw keyboard
 * users back to the top of the page every time a request runs.
 */
export function Button({ variant = "secondary", size = "md", loading = false, icon, children, className, disabled, onClick, ...rest }: ButtonProps) {
  const classes = ["btn", `btn--${variant}`, `btn--${size}`, className].filter(Boolean).join(" ");
  const busy = loading && !disabled;
  return (
    <button type="button" className={classes} disabled={disabled} aria-disabled={busy || undefined} aria-busy={loading || undefined}
      onClick={busy ? (event) => event.preventDefault() /* also stops a submit button submitting its form */ : onClick} {...rest}>
      {loading ? <Spinner size="sm" label="" /> : icon}
      {children}
    </button>
  );
}
