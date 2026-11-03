import type { RouteObject } from "react-router-dom";

import { routes } from "@/app/router";
import { routeTitle } from "@/app/routeTitles";

function paths(list: RouteObject[]): string[] {
  return list.flatMap((r) => [...(r.path ? [r.path] : []), ...paths(r.children ?? [])]);
}

describe("page titles", () => {
  it.each(paths(routes).filter((p) => p !== "*"))("%s has its own title", (path) => {
    const sample = path.replace(/:[^/]+/g, "abc123");
    expect(routeTitle(sample)).not.toBe("Page not found");
  });

  it("unknown addresses are titled as not found", () => {
    expect(routeTitle("/no-such-page")).toBe("Page not found");
    expect(routeTitle("/careers/registered-nurse")).toBe("Page not found");
  });

  it("names the specific kind of page", () => {
    expect(routeTitle("/careers/registered-nurse/questions/m-walk-0")).toBe("Interview question");
    expect(routeTitle("/notes/new")).toBe("New note");
    expect(routeTitle("/saved/collections/c1/practice")).toBe("Practice queue");
    expect(routeTitle("/scenarios/attempts/a1")).toBe("Scenario attempt");
    expect(routeTitle("/problems/")).toBe("Practice library");
  });
});
