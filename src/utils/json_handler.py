from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
import pandas as pd


def load_json_file(file_path: str | Path) -> Any:
    """
    Loads a JSON file and returns its parsed Python object.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    if path.suffix.lower() != ".json":
        raise ValueError(f"File is not a JSON file: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in file {path}: {error.msg} "
            f"at line {error.lineno}, column {error.colno}"
        ) from error


def save_json_file(
    data: Any,
    file_path: str | Path,
    indent: int = 2,
    ensure_ascii: bool = False,
    overwrite: bool = True,
) -> None:
    """
    Saves Python data as a JSON file.

    Args:
        data:
            Python object to save as JSON. Usually dict or list.
        file_path:
            Target path for the JSON file.
        indent:
            JSON indentation level.
        ensure_ascii:
            If False, keeps characters like ä, ö, ü readable.
        overwrite:
            If False, raises an error when the target file already exists.
    """
    path = Path(file_path)

    if path.suffix.lower() != ".json":
        raise ValueError(f"Target file must have .json extension: {path}")

    if path.exists() and not overwrite:
        raise FileExistsError(f"JSON file already exists: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with path.open("w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=ensure_ascii,
                indent=indent,
                default=str,
            )

    except TypeError as error:
        raise TypeError(
            f"Data is not JSON serializable for file {path}: {error}"
        ) from error


def json_to_dataframe(
    data: dict[str, Any] | list[dict[str, Any]] | str,
    root_key: str | None = None,
    flatten_nested: bool = True,
) -> pd.DataFrame:
    """
    Converts JSON-like data into a pandas DataFrame.

    Supported inputs:
    - list[dict]
    - dict with a root key containing a list[dict]
    - JSON string

    Args:
        data:
            Parsed JSON object or JSON string.
        root_key:
            Optional key to extract from a root object.
            Example: root_key="user_profiles" for {"user_profiles": [...]}
        flatten_nested:
            If True, nested objects are flattened using pandas.json_normalize.

    Returns:
        pandas.DataFrame
    """

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON string: {error.msg} "
                f"at line {error.lineno}, column {error.colno}"
            ) from error

    if root_key is not None:
        if not isinstance(data, dict):
            raise TypeError(
                "root_key can only be used when data is a dictionary."
            )

        if root_key not in data:
            raise KeyError(f"Root key not found in JSON data: {root_key}")

        data = data[root_key]

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise TypeError(
            "JSON data must be a list of objects, a single object, "
            "or a dictionary containing a list under root_key."
        )

    if not all(isinstance(item, dict) for item in data):
        raise TypeError("All items in the JSON list must be dictionaries.")

    if flatten_nested:
        return pd.json_normalize(data, sep="_")

    return pd.DataFrame(data)


def parse_json_if_string(data: Any) -> Any:
    """
    Parses data if it is a JSON string.
    Otherwise returns the data unchanged.
    """
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON string: {error.msg} "
                f"at line {error.lineno}, column {error.colno}"
            ) from error

    return data


def concat_json_responses(
    responses: Iterable[dict[str, Any] | list[dict[str, Any]] | str],
    root_key: str,
    skip_empty: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    """
    Concatenates multiple JSON responses from AI calls into one JSON object.

    Expected response format:
        {
            "<root_key>": [
                {...},
                {...}
            ]
        }

    Also supports responses that are directly lists:
        [
            {...},
            {...}
        ]

    Args:
        responses:
            Iterable of JSON responses. Each response may be:
            - parsed dict
            - parsed list of dicts
            - JSON string
        root_key:
            Root key under which records are stored.
            Example: "user_profiles" or "user_mobility_subscriptions".
        skip_empty:
            If True, empty responses are ignored.

    Returns:
        One merged JSON object:
            {
                "<root_key>": [...]
            }
    """
    merged_records: list[dict[str, Any]] = []

    for index, response in enumerate(responses):
        parsed_response = parse_json_if_string(response)

        if parsed_response is None:
            if skip_empty:
                continue

            raise ValueError(f"Response at position {index} is None.")

        if isinstance(parsed_response, dict):
            if root_key not in parsed_response:
                raise KeyError(
                    f"Root key '{root_key}' not found in response at position {index}."
                )

            records = parsed_response[root_key]

        elif isinstance(parsed_response, list):
            records = parsed_response

        else:
            raise TypeError(
                f"Response at position {index} must be dict, list, or JSON string. "
                f"Got {type(parsed_response).__name__}."
            )

        if records is None:
            if skip_empty:
                continue

            raise ValueError(
                f"Records under root key '{root_key}' are None at position {index}."
            )

        if not isinstance(records, list):
            raise TypeError(
                f"Records under root key '{root_key}' must be a list "
                f"at response position {index}. Got {type(records).__name__}."
            )

        if skip_empty and len(records) == 0:
            continue

        for record_index, record in enumerate(records):
            if not isinstance(record, dict):
                raise TypeError(
                    f"Record at response position {index}, record position {record_index} "
                    f"must be a dict. Got {type(record).__name__}."
                )

            merged_records.append(record)

    return {root_key: merged_records}


def dataframe_to_json(
    df: pd.DataFrame,
    root_key: str | None = None,
) -> dict[str, list[dict[str, Any]]] | list[dict[str, Any]]:
    """
    Converts a pandas DataFrame into JSON-compatible Python data.

    Args:
        df:
            pandas DataFrame to convert.
        root_key:
            Optional root key for wrapping the records.
            Example: root_key="user_profiles" returns:
                {"user_profiles": [...]}

    Returns:
        Either:
            - list[dict]
            - dict with root_key and list[dict]
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df).__name__}")

    # Replace pandas NaN/NaT values with None so they become valid JSON null values
    clean_df = df.where(pd.notnull(df), None)

    records = clean_df.to_dict(orient="records")

    if root_key is None:
        return records

    return {root_key: records}
