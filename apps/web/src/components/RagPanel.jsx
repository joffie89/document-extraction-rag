import { useState } from "react";

import { askDocument, prepareRag } from "../api";

/** Prepare a document index and run grounded questions against it. */
export default function RagPanel({ document, onIndexed, onError }) {
  const [strategy, setStrategy] = useState("semantic");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const canPrepare =
    document && ["ready", "indexed"].includes(document.status);
  const canAsk = document?.status === "indexed";

  /** Build the selected chunk index for the current Markdown. */
  async function handlePrepare() {
    setIsPreparing(true);
    setAnswer("");
    setSources([]);

    try {
      const result = await prepareRag(document.id, strategy);
      onIndexed(result);
    } catch (error) {
      onError(error.message);
    } finally {
      setIsPreparing(false);
    }
  }

  /** Ask a grounded question against the active document index. */
  async function handleQuestion(event) {
    event.preventDefault();

    if (!question.trim()) {
      onError("Enter a question before testing RAG.");
      return;
    }

    setIsAsking(true);

    try {
      const result = await askDocument(document.id, question);
      setAnswer(result.answer);
      setSources(result.sources);
    } catch (error) {
      onError(error.message);
    } finally {
      setIsAsking(false);
    }
  }

  return (
    <section className="panel rag-panel" aria-labelledby="rag-heading">
      <div>
        <p className="eyebrow">Step 3</p>
        <h2 id="rag-heading">Prepare and test RAG</h2>
        <p className="panel-copy">
          Choose how the edited Markdown should be indexed with OpenAI
          embeddings and ChromaDB.
        </p>
      </div>

      <fieldset className="strategy-options" disabled={!canPrepare || isPreparing}>
        <legend>Advanced chunking</legend>
        <label
          className={strategy === "semantic" ? "strategy selected" : "strategy"}
        >
          <input
            type="radio"
            name="strategy"
            value="semantic"
            checked={strategy === "semantic"}
            onChange={(event) => setStrategy(event.target.value)}
          />
          <span>
            <strong>Semantic</strong>
            <small>Detect topic changes from embedding distance.</small>
          </span>
        </label>
        <label
          className={
            strategy === "hierarchical" ? "strategy selected" : "strategy"
          }
        >
          <input
            type="radio"
            name="strategy"
            value="hierarchical"
            checked={strategy === "hierarchical"}
            onChange={(event) => setStrategy(event.target.value)}
          />
          <span>
            <strong>Hierarchical</strong>
            <small>Preserve sections and expand retrieved parent context.</small>
          </span>
        </label>
      </fieldset>

      <button
        className="primary-button full-width"
        type="button"
        onClick={handlePrepare}
        disabled={!canPrepare || isPreparing}
      >
        {isPreparing ? "Preparing index…" : "Prepare for RAG"}
      </button>

      <form className="question-form" onSubmit={handleQuestion}>
        <label htmlFor="rag-question">Test a question</label>
        <div className="question-row">
          <input
            id="rag-question"
            type="text"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="What does this document say about…?"
            disabled={!canAsk || isAsking}
          />
          <button
            className="secondary-button"
            type="submit"
            disabled={!canAsk || isAsking}
          >
            {isAsking ? "Asking…" : "Ask"}
          </button>
        </div>
      </form>

      {answer && (
        <article className="answer-card" aria-live="polite">
          <h3>Answer</h3>
          <p>{answer}</p>
          <div className="source-list">
            {sources.map((source, index) => (
              <span key={source.id || index}>
                Source {index + 1}: {source.heading_path || "Document"}
              </span>
            ))}
          </div>
        </article>
      )}
    </section>
  );
}
