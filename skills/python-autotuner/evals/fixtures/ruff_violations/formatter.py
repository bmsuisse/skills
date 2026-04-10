"""String formatter module."""
import json
import re
from typing import Optional


GLOBAL_PREFIX = "PREFIX"


def format_name(first, last, middle=None):
    if middle is not None:
        return first + " " + middle + " " + last
    else:
        return first + " " + last


def build_report(data: list[dict], title: str = "Report") -> str:
    lines = []
    lines.append("=" * 40)
    lines.append(title)
    lines.append("=" * 40)
    for item in data:
        for k, v in item.items():
            lines.append(k + ": " + str(v))
    return "\n".join(lines)


def parse_config(path: str) -> Optional[dict]:
    try:
        with open(path) as f:
            data = json.load(f)
            return data
    except Exception:
        return None


def is_valid_email(email: str) -> bool:
    pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if re.match(pattern, email) is not None:
        return True
    else:
        return False


class ReportBuilder:
    def __init__(self, title, sections=None):
        self.title = title
        self.sections = sections if sections is not None else []

    def add(self, section):
        self.sections.append(section)
        return self

    def render(self) -> str:
        result = ""
        for s in self.sections:
            result = result + s + "\n"
        return result
