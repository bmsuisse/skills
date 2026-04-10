"""CSV/TSV parser — missing type annotations throughout."""


SUPPORTED_DELIMITERS = [",", "\t", ";", "|"]


def detect_delimiter(line: str) -> str:
    """Detect the most likely delimiter in a header line."""
    counts = {d: line.count(d) for d in SUPPORTED_DELIMITERS}
    best = max(counts, key=lambda d: counts[d])
    if counts[best] == 0:
        return ","
    return best


def parse_header(line: str, delimiter: str) -> list[str]:
    """Parse a header row into a list of column names."""
    return [col.strip().lower().replace(" ", "_") for col in line.split(delimiter)]


def parse_row(line: str, delimiter: str, columns: list[str]) -> dict[str, str] | None:
    """Parse a data row into a dict keyed by column name."""
    values = line.split(delimiter)
    if len(values) != len(columns):
        return None
    return {col: val.strip() for col, val in zip(columns, values)}


def parse_csv(text: str, skip_errors: bool = False) -> list[dict[str, str]]:
    """Parse CSV/TSV text into a list of dicts."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    delimiter = detect_delimiter(lines[0])
    columns = parse_header(lines[0], delimiter)

    records: list[dict[str, str]] = []
    for line in lines[1:]:
        row = parse_row(line, delimiter, columns)
        if row is None:
            if not skip_errors:
                raise ValueError(f"Row has wrong number of columns: {line!r}")
        else:
            records.append(row)
    return records


def summarize(
    records: list[dict[str, str]],
    numeric_columns: list[str],
) -> dict[str, dict[str, float]]:
    """Return min/max/avg for specified numeric columns."""
    if not records:
        return {}

    result: dict[str, dict[str, float]] = {}
    for col in numeric_columns:
        values: list[float] = []
        for rec in records:
            val = rec.get(col)
            if val is not None:
                try:
                    values.append(float(val))
                except ValueError:
                    pass
        if values:
            result[col] = {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "count": float(len(values)),
            }
    return result
