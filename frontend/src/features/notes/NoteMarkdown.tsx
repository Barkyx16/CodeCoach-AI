import Markdown from "react-markdown";

/**
 * Notes are untrusted text. react-markdown never renders raw HTML (skipHtml makes that explicit),
 * its default URL transform drops javascript: and other unsafe links, and images are not
 * rendered at all (a remote image would leak that the note was opened).
 */
export function NoteMarkdown({ text }: { text: string }) {
  if (!text.trim()) return <p className="subtle">Nothing written yet.</p>;
  return (
    <div className="markdown note-markdown">
      <Markdown skipHtml disallowedElements={["img"]} unwrapDisallowed
        components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer nofollow">{children}</a> }}>
        {text}
      </Markdown>
    </div>
  );
}
