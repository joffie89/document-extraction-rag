"""OpenAI embedding and grounded-answer functions."""

from openai import OpenAI


def create_embeddings(
    client: OpenAI,
    texts: list[str],
    model: str,
) -> list[list[float]]:
    """Embed non-empty text batches while preserving their input order."""

    if not texts:
        return []
    if any(not text.strip() for text in texts):
        raise ValueError("Embedding inputs cannot be blank")

    response = client.embeddings.create(
        model=model,
        input=texts,
        encoding_format="float",
    )
    embeddings: list[list[float]] = [[] for text in texts]

    for item in response.data:
        if item.index < 0 or item.index >= len(texts):
            raise RuntimeError("OpenAI returned an invalid embedding index")
        embeddings[item.index] = item.embedding

    if any(not embedding for embedding in embeddings):
        raise RuntimeError("OpenAI returned an incomplete embedding batch")

    return embeddings


def generate_grounded_answer(
    client: OpenAI,
    model: str,
    question: str,
    retrieved_chunks: list[dict[str, object]],
    *,
    temperature: float = 0.2,
    strict_grounding: bool = False,
) -> str:
    """Answer from retrieved context and require inline source references."""

    if not question.strip():
        raise ValueError("A question is required")
    if not retrieved_chunks:
        raise ValueError("Retrieved context is required")

    context_blocks = []
    for source_number, chunk in enumerate(retrieved_chunks, start=1):
        heading = str(chunk.get("heading_path") or "Document")
        text = str(chunk["text"])
        context_blocks.append(
            f"[Source {source_number}] {heading}\n{text}",
        )

    context = "\n\n".join(context_blocks)
    instructions = (
        "Answer only from the supplied sources. Cite supporting statements "
        "with [Source N]. If the sources do not contain the answer, say so."
    )
    if strict_grounding:
        instructions += (
            " Never calculate, estimate, infer, or derive a figure that is not "
            "explicitly stated in the sources. If the exact requested figure is "
            "not stated, say that the sources do not state it. Cite only sources "
            "that directly support each sentence, placing the citation in that "
            "sentence."
        )

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=f"Question:\n{question.strip()}\n\nSources:\n{context}",
        max_output_tokens=800,
        temperature=temperature,
        store=False,
    )
    answer = response.output_text.strip()
    if not answer:
        raise RuntimeError("OpenAI returned an empty answer")

    return answer
