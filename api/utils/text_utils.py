import re


def fix_smart_quotes(text):
    if type(text) == str:
        text = (
            text.replace("”", '"').replace("“", '"').replace("’", "'").replace("‘", "'")
        )
        # text = text.encode("ascii", "ignore").decode()
    return text


def replace_links_with_markdown_links(text):
    repl = lambda m: f"[{m.group()}]({m.group()})"
    http_pattern = r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_\+.~#?&\/=]*"
    text = re.sub(http_pattern, repl, text)
    return text
