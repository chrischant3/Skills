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
from bisect import bisect_right

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
        if raw.endswith("\r"):
            raw = raw[:-1]  # Windows line endings; a stray \r stops fences closing
        reader.read(number, raw.expandtabs(TAB_STOP))
    return reader.fenced, reader.fenced | reader.indented


# What the last line was, which decides what the next one can start.
BLANK, PARAGRAPH, CODE, OTHER = "blank", "paragraph", "code", "other"
EMPTY_ITEM = "empty-item"  # a bare list marker, which a blank line then closes


class _Reader:
    """Reads lines in order, keeping the block structure that decides what is code."""

    def __init__(self):
        self.fenced, self.indented = set(), set()
        self.items = []  # content column of each open list item, strictly increasing
        self.fence = None  # (character, length, item depth) of the open fence
        self.html = None  # (end pattern or None, item depth) of the open HTML block
        self.previous = BLANK
        # Where the open paragraph started, for telling a heading underline from
        # a lazy continuation line.
        self.paragraph_column, self.paragraph_quoted = 0, False

    def read(self, number, line):
        text = line.lstrip(" ")
        indent = len(line) - len(text)
        blank = text == ""
        if self.fence and self._continues_fence(number, text, indent, blank):
            return
        if self.html and self._continues_html(text, indent, blank):
            return
        if blank:
            if self.previous == EMPTY_ITEM:
                self.items.pop()  # an item can't start with two blank lines (CommonMark 5.2)
            self.previous = BLANK
            return
        if self.previous == PARAGRAPH and not self._interrupts_paragraph(text, indent):
            return
        while self.items and indent < self.items[-1]:
            self.items.pop()
        self._start_block(number, line, text, indent)

    def _continues_fence(self, number, text, indent, blank):
        character, length, depth = self.fence
        if not blank and depth and indent < self.items[depth - 1]:
            self.fence = None  # the list item holding the fence has ended
            return False
        self.fenced.add(number)
        if not blank and indent - self._column(depth) <= 3:
            run = len(text) - len(text.lstrip(character))
            if run >= length and text[run:].strip(" ") == "":
                self.fence = None
                self.previous = OTHER
        return True

    def _continues_html(self, text, indent, blank):
        end, depth = self.html
        if not blank and depth and indent < self.items[depth - 1]:
            self.html = None
            return False
        if end is None:
            if blank:
                self.html = None
                self.previous = BLANK
            return True
        if end.search(text):
            self.html = None
            self.previous = OTHER
        return True

    def _interrupts_paragraph(self, text, indent):
        # Only some blocks can start on a line straight after paragraph text;
        # anything else continues the paragraph, however it is indented.
        if indent - self._column_for(indent) > 3:
            return False
        if (
            _fence_opening(text)
            or ATX_HEADING.match(text)
            or THEMATIC_BREAK.match(text)
        ):
            return True
        if self._underlines_paragraph(text, indent):
            return True
        if any(start.match(text) for start, _ in HTML_STARTS):
            return True
        if text.startswith(">"):
            return True  # a block quote; its text is then read as a quoted paragraph
        marker = LIST_MARKER.match(text)
        if not marker:
            return False
        has_text = text[marker.end() :].strip() != ""
        starts_at_one = marker.group(2) in (None, "1")
        # A list numbered from 2 can only interrupt as the next item of an open list.
        sibling = bool(self.items) and indent < self.items[-1]
        return has_text and (starts_at_one or sibling)

    def _underlines_paragraph(self, text, indent):
        # An underline turns the paragraph into a heading, but only from inside
        # the paragraph's own container: a lazy line can't be one.
        if not SETEXT_UNDERLINE.match(text) or self.paragraph_quoted:
            return False
        return indent >= self.paragraph_column

    def _start_block(self, number, line, text, indent):
        if indent - self._column() >= 4:
            self.indented.add(number)
            self.previous = CODE
            return
        if self._try_open_fence(number, text) or self._try_open_html(text):
            return
        underline = self.previous == PARAGRAPH and self._underlines_paragraph(
            text, indent
        )
        if THEMATIC_BREAK.match(text) or ATX_HEADING.match(text) or underline:
            self.previous = OTHER
            return
        if LIST_MARKER.match(text):
            self._open_list_items(number, line, indent)
            return
        self._start_paragraph(text)

    def _open_list_items(self, number, line, position):
        # One line can open several items: "- 1. Step" is a list inside a list.
        while True:
            marker = LIST_MARKER.match(line, position)
            content = _content_column(line, marker.end())
            self.items.append(content)
            rest = line[content:]
            opening = rest.lstrip(" ")
            if rest.startswith("    ") and opening:
                # Five or more spaces after the marker: the item opens with code.
                self.indented.add(number)
                self.previous = CODE
                return
            position = content + len(rest) - len(opening)
            if not (opening and LIST_MARKER.match(line, position)):
                break
        if self._try_open_fence(number, opening) or self._try_open_html(opening):
            return
        if opening:
            self._start_paragraph(opening)
        else:
            self.previous = EMPTY_ITEM

    def _start_paragraph(self, text):
        self.previous = PARAGRAPH
        self.paragraph_column = self._column()
        self.paragraph_quoted = text.startswith(">")

    def _try_open_fence(self, number, text):
        """Open a fenced block if text starts one. Returns whether it did."""
        opened = _fence_opening(text)
        if not opened:
            return False
        self.fence = (opened.group(1)[0], len(opened.group(1)), len(self.items))
        self.fenced.add(number)
        self.previous = OTHER
        return True

    def _try_open_html(self, text):
        """Open an HTML block if text starts one. Returns whether it did."""
        starts, end = self._html_start(text)
        if not starts:
            return False
        self.previous = OTHER
        if end is None or not end.search(text):
            self.html = (end, len(self.items))
        return True

    def _html_start(self, text):
        # Returns (starts a block, pattern that ends it or None for a blank line).
        for start, end in HTML_STARTS:
            if start.match(text):
                return True, end
        # Any other tag alone on its line starts a block, unless it follows paragraph text.
        if self.previous != PARAGRAPH and HTML_OTHER_TAG.match(text):
            return True, None
        return False, None

    def _column(self, depth=None):
        depth = len(self.items) if depth is None else depth
        return self.items[depth - 1] if depth else 0

    def _column_for(self, indent):
        # The content column of the innermost list item this line is still inside.
        # Columns increase, so a binary search keeps deep nesting linear overall.
        inside = bisect_right(self.items, indent)
        return self.items[inside - 1] if inside else 0


def _fence_opening(text):
    # A backtick fence's info string can't contain a backtick (CommonMark 4.5).
    opened = FENCE_OPEN.match(text)
    if opened and opened.group(1)[0] == "`" and "`" in opened.group(2):
        return None
    return opened


def _content_column(line, after_marker):
    spaces = len(line) - after_marker - len(line[after_marker:].lstrip(" "))
    if spaces == 0 or spaces > 4 or line[after_marker:].strip() == "":
        # No text after the marker, or five or more spaces: content starts one
        # space after it (and with five or more, the rest is indented code).
        return after_marker + 1
    return after_marker + spaces
