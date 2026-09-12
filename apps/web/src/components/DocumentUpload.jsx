import { useState } from "react";

import { uploadDocument } from "../api";

/** Upload a supported file and report the queued document. */
export default function DocumentUpload({ onUploaded, onError }) {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  /** Submit the selected file to the extraction API. */
  async function handleSubmit(event) {
    event.preventDefault();

    if (!file) {
      onError("Choose a document before uploading.");
      return;
    }

    setIsUploading(true);

    try {
      const document = await uploadDocument(file);
      onUploaded(document);
      setFile(null);
      event.currentTarget.reset();
    } catch (error) {
      onError(error.message);
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section className="panel upload-panel" aria-labelledby="upload-heading">
      <div>
        <p className="eyebrow">Step 1</p>
        <h2 id="upload-heading">Extract a document</h2>
        <p className="panel-copy">
          Upload any format supported by the installed Docling release. OCR is
          configured for English.
        </p>
      </div>

      <form className="upload-form" onSubmit={handleSubmit}>
        <label className="file-picker">
          <span>{file ? file.name : "Choose a document"}</span>
          <input
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>
        <button className="primary-button" type="submit" disabled={isUploading}>
          {isUploading ? "Uploading…" : "Upload and extract"}
        </button>
      </form>
    </section>
  );
}
