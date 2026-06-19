from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping


PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


def read_markdown_file(path: str | Path) -> str:
    """
    Reads a Markdown prompt file as UTF-8 text.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Prompt path is not a file: {file_path}")

    return file_path.read_text(encoding="utf-8").strip()


def format_prompt_value(value: Any) -> str:
    """
    Converts Python values into prompt-safe strings.

    Dicts and lists are rendered as formatted JSON so that they remain
    easy to read and easy for the model to interpret.
    """
    if value is None:
        return "null"

    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)

    return str(value)


def render_template(template: str, context: Mapping[str, Any]) -> str:
    """
    Replaces placeholders like {{num_profiles}} with values from context.
    """

    missing_keys: set[str] = set()

    def replace_match(match: re.Match[str]) -> str:
        key = match.group(1)

        if key not in context:
            missing_keys.add(key)
            return match.group(0)

        return format_prompt_value(context[key])

    rendered = PLACEHOLDER_PATTERN.sub(replace_match, template)

    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise KeyError(f"Missing prompt context value(s): {missing}")

    return rendered


def join_prompt_files(
    prompt_root: str | Path,
    relative_files: list[str],
    include_file_headers: bool = True,
) -> str:
    """
    Reads and joins multiple prompt files.
    """
    prompt_root = Path(prompt_root)
    sections: list[str] = []

    for relative_file in relative_files:
        file_path = prompt_root / relative_file
        content = read_markdown_file(file_path)

        if include_file_headers:
            sections.append(f"<!-- Prompt file: {relative_file} -->\n\n{content}")
        else:
            sections.append(content)

    return "\n\n---\n\n".join(sections)


def build_ai_messages(
    prompt_root: str | Path,
    prompt_group: str,
    context: Mapping[str, Any],
    shared_files: list[str] | None = None,
    group_files: list[str] | None = None,
) -> list[dict[str, str]]:
    """
    Builds chat-style messages for an AI call from Markdown prompt files.

    The shared files become the system message.
    The group-specific files become the user message.

    Example:
        messages = build_ai_messages(
            prompt_root="prompts",
            prompt_group="user_profiles",
            context={
                "num_profiles": 10,
                "target_locations": ["Berlin", "Cologne", "Frankfurt"],
                "persona_seed_context": [],
                "additional_constraints": "Focus on urban mobility users.",
                "output_schema": "...",
            },
        )
    """

    if shared_files is None:
        shared_files = [
            "shared/system.md",
            "shared/json_output_rules.md",
            "shared/synthetic_data_rules.md",
        ]

    if group_files is None:
        group_files = [
            f"{prompt_group}/prompt.md",
            f"{prompt_group}/output_schema.md",
            f"{prompt_group}/generation_rules.md",
        ]

    system_content = join_prompt_files(
        prompt_root=prompt_root,
        relative_files=shared_files,
    )

    user_template = join_prompt_files(
        prompt_root=prompt_root,
        relative_files=group_files,
    )

    user_content = render_template(
        template=user_template,
        context=context,
    )

    return [
        {
            "role": "system",
            "content": system_content,
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]