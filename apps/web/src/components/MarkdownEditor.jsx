import { useEffect, useState } from "react";

import { fetchMarkdown, updateMarkdown } from "../api";

/** Load, edit, and save the selected document's Markdown. */
export default function MarkdownEditor({ document, onSaved, onError }) {
  const [markdown, setMarkdown] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const markdownReady =
    document && ["ready", "indexed"].includes(document.status);

  useEffect(() => {
    let cancelled = false;

    if (!markdownReady) {
      setMarkdown("");
      return () => {
        cancelled = true;
      };
    }

    setIsLoading(true);
    fetchMarkdown(document.id)
      .then((payload) => {
        if (!cancelled) {
          setMarkdown(payload.markdown);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          onError(error.message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [document?.id, document?.status, markdownReady, onError]);

  /** Persist the current Markdown and invalidate any previous index. */
  async function handleSave() {
    setIsSaving(true);

    try {
      const updatedDocument = await updateMarkdown(document.id, markdown);
      onSaved(updatedDocument);
    } catch (error) {
      onError(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="panel editor-panel" aria-labelledby="editor-heading">
      <div className="panel-heading-row">
        <div>
          <p className="eyebrow">Step 2</p>
          <h2 id="editor-heading">Review the Markdown</h2>
        </div>
        {document && (
          <span className={`status status-${document.status}`}>
            {document.status}
          </span>
        )}
      </div>

      {!document && (
        <p className="empty-state">Select an uploaded document to review it.</p>
      )}

      {document && !markdownReady && (
        <p className="empty-state">
          Extraction is {document.status}. The editor will unlock when Markdown
          is ready.
        </p>
      )}

      {markdownReady && (
        <>
          <textarea
            className="markdown-editor"
            aria-label="Extracted Markdown"
            value={markdown}
            onChange={(event) => setMarkdown(event.target.value)}
            disabled={isLoading || isSaving}
            spellCheck="true"
          />
          <div className="editor-actions">
            <span>{isLoading ? "Loading Markdown…" : `${markdown.length} characters`}</span>
            <button
              className="secondary-button"
              type="button"
              onClick={handleSave}
              disabled={isLoading || isSaving}
            >
              {isSaving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
