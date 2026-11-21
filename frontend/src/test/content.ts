/** Default stand-ins for content metadata and reports (tests override what they check). */
import { http, HttpResponse } from "msw";

import type { ContentMeta } from "@/api/types";

const API = "http://localhost:8000";

export function contentMeta(over: Partial<ContentMeta> = {}): ContentMeta {
  return {
    content_type: "question", content_id: "registered-nurse/m-pressure-0", version: 1, version_label: "Version 1",
    career: "Registered Nurse", topic: "patient assessment", level: "medium", status: "active", retired_reason: null,
    labels: [
      { key: "generated", text: "Generated from the Registered Nurse career profile by CodeCoach's question templates" },
      { key: "not_expert_reviewed", text: "Not reviewed by a subject-matter expert" },
    ],
    changes: [],
    ...over,
  };
}

export const contentHandlers = [
  http.get(`${API}/api/v1/content/:type/*`, ({ params, request }) => {
    const id = new URL(request.url).pathname.split(`/content/${String(params.type)}/`)[1]!.replace(/\/meta$/, "");
    return HttpResponse.json(contentMeta({
      content_type: params.type as ContentMeta["content_type"], content_id: decodeURIComponent(id),
      ...(params.type === "problem" ? { version_label: "Test version 1", career: "Software Engineer (coding)", labels: [
        { key: "generated", text: "Generated for CodeCoach's coding problem bank" },
        { key: "tests_not_checked", text: "Tests haven't been checked against a reference solution on this server" },
        { key: "not_expert_reviewed", text: "Not reviewed by a subject-matter expert" },
      ] } : {}),
    }));
  }),
  http.get(`${API}/api/v1/me/reports`, () => HttpResponse.json([])),
];
