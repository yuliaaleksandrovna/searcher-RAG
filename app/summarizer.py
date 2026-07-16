import os


def summarize(query: str, context: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return _with_claude(query, context, api_key)
    return _extractive(query, context)


def _with_claude(query: str, context: str, api_key: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a helpful assistant. Based on the search results below, "
                    f"write a concise answer to the query: '{query}'\n\n"
                    f"Search results:\n{context}\n\n"
                    f"Answer in 2-4 sentences."
                ),
            }],
        )
        return message.content[0].text
    except Exception as e:
        return f"LLM summarization failed: {e}"


def _extractive(query: str, context: str) -> str:
    query_words = {w.lower() for w in query.split() if len(w) > 3}
    sentences = [
        s.strip()
        for s in context.replace("\n", " ").split(".")
        if len(s.strip()) > 40
    ]
    scored = sorted(
        sentences,
        key=lambda s: sum(1 for w in query_words if w in s.lower()),
        reverse=True,
    )
    top = scored[:3]
    return ". ".join(top) + "." if top else context[:400]
