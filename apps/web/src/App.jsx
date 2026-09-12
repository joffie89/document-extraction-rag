import { useCallback, useEffect, useState } from "react";

import { fetchDocuments } from "./api";
import DocumentUpload from "./components/DocumentUpload";
import MarkdownEditor from "./components/MarkdownEditor";
import RagPanel from "./components/RagPanel";

/** Coordinate the upload, editing, and RAG workspace. */
export default function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const selectedDocument =
    documents.find((document) => document.id === selectedId) || null;

  /** Refresh document processing states from the API. */
  const loadDocuments = useCallback(async () => {
    try {
      const latestDocuments = await fetchDocuments();
      setDocuments(latestDocuments);
      setSelectedId((currentId) => {
        const currentStillExists = latestDocuments.some(
          (document) => document.id === currentId,
        );

        if (currentStillExists) {
          return currentId;
        }

        return latestDocuments[0]?.id || null;
      });
    } catch (requestError) {
      setError(requestError.message);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
    const refreshTimer = window.setInterval(loadDocuments, 3000);

    return () => window.clearInterval(refreshTimer);
  }, [loadDocuments]);

  /** Display an error and clear any stale success notice. */
  const showError = useCallback((message) => {
    setError(message);
    setNotice("");
  }, []);

  /** Select a newly queued upload and add it to the document list. */
  function handleUploaded(document) {
    setDocuments((current) => [
      document,
      ...current.filter((item) => item.id !== document.id),
    ]);
    setSelectedId(document.id);
    setError("");
    setNotice("Upload stored. Docling extraction is running in the background.");
  }

  /** Merge a saved Markdown state into the visible document list. */
  function handleSaved(updatedDocument) {
    setDocuments((current) =>
      current.map((document) =>
        document.id === updatedDocument.id ? updatedDocument : document,
      ),
    );
    setError("");
    setNotice("Markdown saved. Prepare the document again to refresh its index.");
  }

  /** Mark the selected document as indexed after RAG preparation. */
  function handleIndexed(result) {
    setDocuments((current) =>
      current.map((document) => {
        if (document.id !== result.document_id) {
          return document;
        }

        return {
          ...document,
          status: result.status,
          chunking_strategy: result.strategy,
        };
      }),
    );
    setError("");
    setNotice(
      `${result.chunk_count} ${result.strategy} chunks are ready in ChromaDB.`,
    );
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <div>
          <p className="brand-kicker">Local document intelligence</p>
          <h1>Document Extraction + RAG</h1>
        </div>
        <div className="model-badge">
          <span>OpenAI</span>
          <strong>3-small · GPT-4.1 mini</strong>
        </div>
      </header>

      {(error || notice) && (
        <div className={error ? "message error-message" : "message notice-message"}>
          <span>{error || notice}</span>
          <button
            type="button"
            aria-label="Dismiss message"
            onClick={() => {
              setError("");
              setNotice("");
            }}
          >
            ×
          </button>
        </div>
      )}

      <main>
        <DocumentUpload onUploaded={handleUploaded} onError={showError} />

        <div className="workspace-grid">
          <aside className="document-list" aria-label="Uploaded documents">
            <div className="document-list-heading">
              <span>Documents</span>
              <span>{documents.length}</span>
            </div>
            {documents.length === 0 && (
              <p className="empty-state compact">No uploads yet.</p>
            )}
            {documents.map((document) => (
              <button
                key={document.id}
                type="button"
                className={
                  document.id === selectedId
                    ? "document-item selected"
                    : "document-item"
                }
                onClick={() => setSelectedId(document.id)}
              >
                <span className="document-name">{document.original_name}</span>
                <span className="document-meta">
                  {document.status}
                  {document.chunking_strategy && ` · ${document.chunking_strategy}`}
                </span>
              </button>
            ))}
          </aside>

          <MarkdownEditor
            document={selectedDocument}
            onSaved={handleSaved}
            onError={showError}
          />

          <RagPanel
            document={selectedDocument}
            onIndexed={handleIndexed}
            onError={showError}
          />
        </div>
      </main>

      <footer>
        Single-user MVP · Local Docker storage · Server-owned OpenAI key
      </footer>
    </div>
  );
}
