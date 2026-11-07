import { useCapabilities } from "@/api/queries";

/**
 * Shown only by a server that can't send email (CodeCoach running on someone's own computer with
 * no mail server set up): nothing was sent, and the email is printed in the terminal running the
 * server instead. A real deployment always sends email, so this never appears there.
 */
export function EmailNotSentNote({ what }: { what: string }) {
  const { data } = useCapabilities();
  if (data?.emails_delivered !== false) return null;
  return (
    <p className="banner banner--info" role="note">
      This copy of CodeCoach isn't set up to send email, so nothing went to your inbox. The {what} is
      printed in the terminal window where the server is running (where you started <code>./dev.sh</code>).
    </p>
  );
}
