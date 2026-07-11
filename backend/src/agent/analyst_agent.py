# Fetch the versioned system prompt from Langfuse (falls back to the local
    # copy when Langfuse is disabled or unreachable); link it to the trace so the
    # Generation shows exactly which prompt version produced the memo.
    prompt = get_prompt("analyst-memo", fallback=_SYSTEM_PROMPT_FALLBACK, type="text")
    system_prompt = prompt.compile() if prompt is not None else _SYSTEM_PROMPT_FALLBACK

    llm = get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"The customer is {name}. Below is the complete grounded data — the "
                "analysis, forecast, optimizer results and the tariff documents "
                "relevant to the recommended plans, all as JSON. Write the "
                "recommendation memo using only these figures.\n\n"
                + json.dumps(grounding, ensure_ascii=False, default=str)
            )
        ),
    ]

    # One retry: the LLM occasionally merges english/german into one field instead of
    # keeping them separate (see backend-review addendum 2026-07-08). Re-prompting once
    # with the bad reply in context reliably re-separates them; a second failure falls
    # back to the deterministic template memo via the caller's except-clause.
    with trace(
        "analyst-memo",
        user_id=user_id,
        tags=["analyst", "memo", "analyze-pipeline"],
        metadata={"memo_source": "llm"},
    ) as tr:
        trace_id = tr.trace_id
        for attempt in range(2):
            response = llm.invoke(messages, config=tr.config(prompt=prompt))
            data = _extract_json(response.content)
            if not data or "english" not in data or "german" not in data:
                raise ValueError("Analyst memo response missing english/german keys")
            
            english, german = data["english"], data["german"]
            if not _looks_like_language_mix(english, german):
                return english, german, trace_id
                
            if attempt == 0:
                messages += [
                    AIMessage(content=response.content),
                    HumanMessage(
                        content=(
                            "Your reply mixed the two languages into one field (or "
                            "duplicated one field's content into the other). Reply again "
                            "with STRICT JSON only: {\"english\": \"<memo>\", "
                            "\"german\": \"<memo>\"} where each field is a complete, "
                            "self-contained memo in exactly one language, with no "
                            "separators or repeated content."
                        )
                    ),
                ]

    raise ValueError("Analyst memo mixed english/german after retry")