import { waitFor } from "@testing-library/react";
import type { UserEvent } from "@testing-library/user-event";

/** Choose a job in the job search box (CareerSelect) as a person does: type part of its name,
 * then click it in the matches. `slug` identifies the job; its words are what gets typed. */
export async function chooseCareer(user: UserEvent, box: HTMLElement, slug: string): Promise<void> {
  await waitFor(() => expect(box).toBeEnabled());
  await user.clear(box);
  await user.type(box, slug.replace(/-/g, " "));
  const option = await waitFor(() => {
    const found = document.querySelector<HTMLElement>(`[role="option"][data-value="${slug}"]`);
    if (!found) throw new Error(`no option for ${slug}`);
    return found;
  });
  await user.click(option);
}
