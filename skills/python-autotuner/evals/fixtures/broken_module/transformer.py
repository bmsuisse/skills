"""String transformer — broken: syntax error + runtime bug."""


def to_snake_case(text: str) -> str
    """Convert CamelCase or spaces to snake_case."""
    import re
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', text)
    s = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s)
    return s.lower().replace(' ', '_').replace('-', '_')


def truncate(text: str, max_len: int = 80, suffix: str = '...') -> str:
    """Truncate text to max_len, appending suffix if truncated."""
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix


def count_words(text: str) -> dict:
    """Return word frequency dict, case-insensitive."""
    words = text.lower().split()
    counts = {}
    for word in words:
        # strip punctuation from edges
        word = word.strip('.,!?;:\'"()[]{}')
        if word:
            counts[word] = counts.get(word, 0) + 1
    return counts


def reverse_words(text: str) -> str
    """Reverse the order of words in a string."""
    return ' '.join(text.split()[::-1])
