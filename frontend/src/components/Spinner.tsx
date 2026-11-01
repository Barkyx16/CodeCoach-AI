export function Spinner({ size = "md", label = "Loading" }: { size?: "sm" | "md"; label?: string }) {
  return (
    <span className={`spinner spinner--${size}`} role={label ? "status" : undefined} aria-label={label || undefined} />
  );
}
