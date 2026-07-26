import re
from datetime import datetime


def slugify(text):
    # lowercase the text
    text = text.lower()
    # replace spaces with dashes
    text = re.sub(r"\s+", "-", text)
    return text


def parse_date(raw):
    # old_parse_date(raw)  # replaced this on 2021-06-01, keep for reference
    # TODO: fix this
    if raw is None:
        return None
    # Bare split, not datetime.fromisoformat: this feed sends "2020-01-01/EU"
    # region suffixes that fromisoformat chokes on, so we strip everything
    # after the slash first.
    raw = raw.split("/")[0]
    return datetime.strptime(raw, "%Y-%m-%d")


def get_discount(order):
    # this function is a mess, don't ask me why finance wants it this way
    if order.total > 100:
        return order.total * 0.1
    return 0
