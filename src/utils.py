import re


def format_disease_name(name: str) -> str:
    """Normalize disease names to: one comma+space between synonyms,
    remove leading ids or leading '%'/'#', and capitalize words.

    Examples:
      '%1234 cirrhosis; familial CIRRHOSIS' -> 'Cirrhosis, Familial Cirrhosis'
    """
    if not name:
        return name

    s = name.strip()

    # Remove leading % or # characters
    s = re.sub(r'^[%#\s]+', '', s)

    # Remove leading IDs like 'OMIM:12345', 'HP:0000001' or plain numeric ids
    s = re.sub(r'^(?:[A-Za-z]+:\d+|\d+)\s*', '', s)

    # Remove stray % and # anywhere
    s = s.replace('%', '').replace('#', '')

    # Split on common separators (comma, semicolon, pipe, slash, dash)
    parts = re.split(r"\s*(?:,|;|\||/|—|-)\s*", s)
    parts = [p.strip() for p in parts if p.strip()]

    # Capitalize each part (title case) and ensure single ', ' separator
    parts = [p.title() for p in parts]

    return ', '.join(parts)
