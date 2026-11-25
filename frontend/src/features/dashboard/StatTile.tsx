import { Card } from "@/components/Card";
import { Icon, type IconName } from "@/components/Icon";

export function StatTile({ label, value, detail, icon, fraction }: {
  label: string; value: string; detail?: string; icon: IconName; fraction?: number;
}) {
  return (
    <Card className="stat">
      <Icon className="stat__icon" name={icon} size={18} />
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
      {detail && <span className="subtle">{detail}</span>}
      {/* Decorative: the detail line already says "of N problems". */}
      {fraction !== undefined && (
        <span className="stat__bar" aria-hidden="true"><span style={{ width: `${Math.min(fraction, 1) * 100}%` }} /></span>
      )}
    </Card>
  );
}
