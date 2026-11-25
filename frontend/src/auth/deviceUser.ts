import type { User } from "@/api/types";
import { storage } from "@/lib/storage";

/**
 * Which account last used this device: id and display name only, never a token. Lets the app,
 * when it can't reach the server, keep showing that person's drafts on this device (they're
 * stored per account) instead of treating them as signed out. Removed on sign-out.
 */
export interface DeviceUser {
  id: string;
  display_name: string | null;
  career_track: string | null;
  is_guest: boolean;
}

export const DEVICE_USER_KEY = "codecoach.device-user.v1";

export function rememberDeviceUser(user: User): void {
  const record: DeviceUser = { id: user.id, display_name: user.display_name ?? null, career_track: user.career_track ?? null, is_guest: user.is_guest };
  storage.set(DEVICE_USER_KEY, JSON.stringify(record));
}

export function readDeviceUser(): DeviceUser | null {
  try {
    const value: unknown = JSON.parse(storage.get(DEVICE_USER_KEY) ?? "null");
    if (value && typeof value === "object" && typeof (value as DeviceUser).id === "string") return value as DeviceUser;
  } catch {
    /* corrupt: ignore */
  }
  return null;
}

export function forgetDeviceUser(): void {
  storage.remove(DEVICE_USER_KEY);
}
