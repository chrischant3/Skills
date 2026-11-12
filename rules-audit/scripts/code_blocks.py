"""Find which lines of a Markdown file are code, following CommonMark 0.31.

Models what decides whether a line is code: fenced code blocks (section
4.5), indented code blocks (4.4), HTML blocks (4.6, inside which a fence is
just text), paragraphs, headings and thematic breaks, and list items (5.2),
whose content column moves where code can start. Block quotes are not
modelled: their lines are read as paragraph text, so a fence inside one is
reported as not code. That errs towards "not code", the safe side for an
audit that excuses placeholders found in examples.

One pass over the lines, so the time taken grows linearly with the file.
Standard library only, Python 3.10 or later.
"""

import re

TAB_STOP = 4
FENCE_OPEN = re.compile(r"(`{3,}|~{3,})(.*)$")
LIST_MARKER = re.compile(r"([-+*]|(\d{1,9})[.)])(?=[ ]|$)")
THEMATIC_BREAK = re.compile(r"([-*_])(?:[ ]*\1){2,}[ ]*$")
ATX_HEADING = re.compile(r"#{1,6}(?:[ ]|$)")
SETEXT_UNDERLINE = re.compile(r"(?:=+|-+)[ ]*$")

# HTML block starts (CommonMark 4.6), each with the text that ends the block;
# None means the block ends at a blank line.
HTML_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|"
    "colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|"
    "footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|"
    "link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|"
    "section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)
HTML_STARTS = [
    (
        re.compile(r"<(?:script|pre|style|textarea)(?:[ >]|$)", re.I),
        re.compile(r"</(?:script|pre|style|textarea)>", re.I),
    ),
    (re.compile(r"<!--"), re.compile(r"-->")),
    (re.compile(r"<\?"), re.compile(r"\?>")),
    (re.compile(r"<![A-Za-z]"), re.compile(r">")),
    (re.compile(r"<!\[CDATA\["), re.compile(r"\]\]>")),
    (re.compile(rf"</?(?:{HTML_BLOCK_TAGS})(?:[ >]|/>|$)", re.I), None),
]
# Any other complete tag alone on its line starts a block, but can't interrupt a paragraph.
# Attribute names can't hold spaces, so each space has one place in the
# match; a looser pattern backtracked exponentially on a line of short words.
HTML_ATTRIBUTE = (
    r"""[ ]+[A-Za-z_:][A-Za-z0-9_.:-]*(?:[ ]*=[ ]*(?:"[^"]*"|'[^']*'|[^ "'=<>`]+))?"""
)
HTML_OTHER_TAG = re.compile(
    rf"(?:<[A-Za-z][A-Za-z0-9-]*(?:{HTML_ATTRIBUTE})*[ ]*/?>|</[A-Za-z][A-Za-z0-9-]*[ ]*>)[ ]*$"
)


def code_lines(lines):
    """Return (fenced, code): sets of 1-based line numbers.

    fenced holds the lines of fenced code blocks, fence lines included.
    code holds those plus the non-blank lines of indented code blocks.
    """
    reader = _Reader()
    for number, raw in enumerate(lines, start=1):
        reader.read(number, raw.expandtabs(TAB_STOP))
    return reader.fenced, reader.fenced | reader.indented


class _Reader:
    """Reads lines in order, keeping the block structure that decides what is code."""

    def __init__(self):
        self.fenced, self.indented = set(), set()
        self.items = []  # content column of each open list item, innermost last
        self.fence = None  # (character, length, item depth) of the open fence
        self.html = None  # (end pattern or None, item depth) of the open HTML block
        # The last line: blank | paragraph | code | other | empty-item (a bare list marker).
        self.previous = "blank"

    def read(self, number, line):
        text = line.lstrip(" ")
        indent = len(line) - len(text)
        blank = text == ""
        if self.fence and self._continues_open_block(number, text, indent, blank):
            return
        if self.html and self._continues_html(text, indent, blank):
            return
        if blank:
            if self.previous == "empty-item":
                self.items.pop()  # an item can't start with two blank lines (CommonMark 5.2)
            self.previous = "blank"
            return
        continues_paragraph = self.previous == "paragraph"
        if continues_paragraph and not self._interrupts_paragraph(text, indent):
            return
        while self.items and indent < self.items[-1]:
            self.items.pop()
        self._start_block(number, line, text, indent - self._column())

    def _continues_open_block(self, number, text, indent, blank):
        character, length, depth = self.fence
        if not blank and depth and indent < self.items[depth - 1]:
            self.fence = None  # the list item holding the fence has ended
            return False
        self.fenced.add(number)
        if not blank and indent - self._column(depth) <= 3:
            run = len(text) - len(text.lstrip(character))
            if run >= length and text[run:].strip(" ") == "":
                self.fence = None
                self.previous = "other"
        return True

    def _continues_html(self, text, indent, blank):
        end, depth = self.html
        if not blank and depth and indent < self.items[depth - 1]:
            self.html = None
            return False
        if end is None:
            if blank:
                self.html = None
                self.previous = "blank"
            return True
        if end.search(text):
            self.html = None
            self.previous = "other"
        return True

    def _interrupts_paragraph(self, text, indent):
        # Only some blocks can start on a line straight after paragraph text;
        # anything else continues the paragraph, however it is indented.
        column = self._column_for(indent)
        if indent - column > 3:
            return False
        if FENCE_OPEN.match(text) and _is_fence_opening(FENCE_OPEN.match(text)):
            return True
        if ATX_HEADING.match(text) or THEMATIC_BREAK.match(text):
            return True
        if SETEXT_UNDERLINE.match(text):
            return True
        if any(start.match(text) for start, _ in HTML_STARTS):
            return True
        marker = LIST_MARKER.match(text)
        if marker:
            starts_at_one = marker.group(2) is None or marker.group(2) == "1"
            has_text = text[marker.end() :].strip() != ""
            return has_text and (starts_at_one or bool(self.items))
        return False

    def _start_block(self, number, line, text, relative):
        if relative >= 4:
            self.indented.add(number)
            self.previous = "code"
            return
        if self._opens_fence(number, text):
            return
        underline = self.previous == "paragraph" and SETEXT_UNDERLINE.match(text)
        if THEMATIC_BREAK.match(text) or ATX_HEADING.match(text) or underline:
            self.previous = "other"
            return
        if self._opens_html(text):
            return
        marker = LIST_MARKER.match(text)
        if marker:
            indent = len(line) - len(text)
            content = _content_column(line, indent + marker.end())
            self.items.append(content)
            rest = line[content:]
            opening = rest.lstrip(" ")
            if rest.startswith("    ") and opening:
                # Five or more spaces after the marker: the item opens with code.
                self.indented.add(number)
                self.previous = "code"
            elif not self._opens_fence(number, opening) and not self._opens_html(
                opening
            ):
                self.previous = "paragraph" if rest.strip() else "empty-item"
            return
        self.previous = "paragraph"

    def _opens_fence(self, number, text):
        opened = FENCE_OPEN.match(text)
        if not (opened and _is_fence_opening(opened)):
            return False
        self.fence = (opened.group(1)[0], len(opened.group(1)), len(self.items))
        self.fenced.add(number)
        self.previous = "other"
        return True

    def _opens_html(self, text):
        for start, end in HTML_STARTS:
            if start.match(text):
                break
        else:
            if self.previous == "paragraph" or not HTML_OTHER_TAG.match(text):
                return False
            end = None
        self.previous = "other"
        if end is None or not end.search(text):
            self.html = (end, len(self.items))
        return True

    def _column(self, depth=None):
        depth = len(self.items) if depth is None else depth
        return self.items[depth - 1] if depth else 0

    def _column_for(self, indent):
        # The content column of the innermost list item this line is still inside.
        for column in reversed(self.items):
            if indent >= column:
                return column
        return 0


def _is_fence_opening(match):
    # A backtick fence's info string can't contain a backtick (CommonMark 4.5).
    return not (match.group(1)[0] == "`" and "`" in match.group(2))


def _content_column(line, after_marker):
    spaces = len(line) - after_marker - len(line[after_marker:].lstrip(" "))
    if spaces == 0 or spaces > 4 or line[after_marker:].strip() == "":
        # One space after the marker; with five or more, the rest is indented code.
        return after_marker + 1
    return after_marker + spaces
