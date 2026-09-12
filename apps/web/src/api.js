const API_PREFIX = "/api/v1";

/** Send one API request and surface a readable server error. */
async function request(path, options = {}) {
  const response = await fetch(`${API_PREFIX}${path}`, options);

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const errorBody = await response.json();
      message = errorBody.detail || message;
    } catch {
      // Keep the status-based message when the server did not return JSON.
    }

    throw new Error(message);
  }

  return response.json();
}

/** Upload a document for background extraction. */
export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  return request("/documents", {
    method: "POST",
    body: formData,
  });
}

/** Fetch all uploaded documents. */
export async function fetchDocuments() {
  return request("/documents");
}

/** Fetch the latest editable Markdown. */
export async function fetchMarkdown(documentId) {
  return request(`/documents/${documentId}/markdown`);
}

/** Save a user-edited Markdown revision. */
export async function updateMarkdown(documentId, markdown) {
  return request(`/documents/${documentId}/markdown`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ markdown }),
  });
}

/** Build the selected RAG index. */
export async function prepareRag(documentId, strategy) {
  return request(`/documents/${documentId}/rag`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ strategy }),
  });
}

/** Ask a question against an indexed document. */
export async function askDocument(documentId, question) {
  return request(`/documents/${documentId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}
