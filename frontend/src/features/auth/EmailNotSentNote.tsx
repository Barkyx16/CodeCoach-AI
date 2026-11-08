import { useCapabilities } from "@/api/queries";

/**
 * Shown only by a server that can't send email (CodeCoach running on someone's own computer with
 * no mail server set up): nothing was sent. The console transport (the default for ./dev.sh) prints
 * the email in the terminal running the server; the file transport (automated tests) saves it in
 * the server's EMAIL_FILE_DIR folder. A real deployment always sends email (production refuses to
 * start without SMTP), so this never appears there, and no page ever shows a code itself.
 */
export function EmailNotSentNote({ what, transport }: { what: string; transport?: string }) {
  const { data } = useCapabilities();
  if (data?.emails_delivered !== false && (transport === undefined || transport === "smtp")) return null;
  if (transport === "file") {
    return (
      <p className="banner banner--info" role="note">
        This copy of CodeCoach isn't set up to send email, so nothing went to your inbox. The {what} was saved as a
        file on the server, in the folder named by its <code>EMAIL_FILE_DIR</code> setting.
      </p>
    );
  }
  return (
    <p className="banner banner--info" role="note">
      This copy of CodeCoach isn't set up to send email, so nothing went to your inbox. The {what} is
      printed in the terminal window where the server is running (where you started <code>./dev.sh</code>).
    </p>
  );
}
