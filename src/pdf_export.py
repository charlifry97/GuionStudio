# pdf_export.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Exportación a PDF sin dependencias externas.

Genera un PDF 1.4 con las cuatro fuentes base Times-* y tamaño A4 con
márgenes de 2,5 cm. Maqueta el guion con el formato editorial estándar:
escenas en negrita, personajes centrados, diálogos con doble sangría,
acotaciones en cursiva y transiciones alineadas a la derecha.
"""

import io

from .parser import classify

PAGE_W = 595.28
PAGE_H = 841.89
MARGIN = 70.87  # 2,5 cm

_TIMES_WIDTHS = {
    ' ': 250, '!': 333, '"': 408, '#': 500, '$': 500, '%': 833, '&': 778,
    "'": 180, '(': 333, ')': 333, '*': 500, '+': 564, ',': 250, '-': 333,
    '.': 250, '/': 278, '0': 500, '1': 500, '2': 500, '3': 500, '4': 500,
    '5': 500, '6': 500, '7': 500, '8': 500, '9': 500, ':': 278, ';': 278,
    '<': 564, '=': 564, '>': 564, '?': 444, '@': 921,
    'A': 722, 'B': 667, 'C': 667, 'D': 722, 'E': 611, 'F': 556, 'G': 722,
    'H': 722, 'I': 333, 'J': 389, 'K': 722, 'L': 611, 'M': 889, 'N': 722,
    'O': 722, 'P': 556, 'Q': 722, 'R': 667, 'S': 556, 'T': 611, 'U': 722,
    'V': 722, 'W': 944, 'X': 722, 'Y': 722, 'Z': 611,
    '[': 333, '\\': 278, ']': 333, '^': 469, '_': 500, '`': 333,
    'a': 444, 'b': 500, 'c': 444, 'd': 500, 'e': 444, 'f': 333, 'g': 500,
    'h': 500, 'i': 278, 'j': 278, 'k': 500, 'l': 278, 'm': 778, 'n': 500,
    'o': 500, 'p': 500, 'q': 500, 'r': 333, 's': 389, 't': 278, 'u': 500,
    'v': 500, 'w': 722, 'x': 500, 'y': 500, 'z': 444,
    '{': 480, '|': 200, '}': 480, '~': 541,
}

_ACCENT_MAP = {
    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
    'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
    'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U', 'ç': 'c', 'Ç': 'C',
}


def _char_width(ch, size):
    return _TIMES_WIDTHS.get(_ACCENT_MAP.get(ch, ch), 500) * size / 1000.0


def _text_width(text, size):
    return sum(_char_width(c, size) for c in text)


def _wrap_line(text, size, max_width):
    if not text:
        return ['']
    lines, current = [], ''
    for word in text.split(' '):
        candidate = (current + ' ' + word) if current else word
        if _text_width(candidate, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or ['']


def _escape_pdf_text(s):
    out = []
    for ch in s:
        code = ord(ch)
        if ch == '(':
            out.append('\\(')
        elif ch == ')':
            out.append('\\)')
        elif ch == '\\':
            out.append('\\\\')
        elif 32 <= code < 127:
            out.append(ch)
        elif 160 <= code <= 255:
            out.append('\\' + format(code, '03o'))
        else:
            out.append('?')
    return ''.join(out)


class _PDFDocument:
    def __init__(self):
        self._buffer = io.BytesIO()
        self._buffer.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        self._offsets = {}
        self._pages = []
        self._current = []
        self._y = PAGE_H - MARGIN

    def _flush_page(self):
        if self._current:
            self._pages.append(self._current)
        self._current = []
        self._y = PAGE_H - MARGIN

    def _check_space(self, needed):
        if self._y - needed < MARGIN:
            self._flush_page()

    @staticmethod
    def _font(bold, italic):
        if bold and italic:
            return 'F4'
        if bold:
            return 'F2'
        if italic:
            return 'F3'
        return 'F1'

    def write_line(self, text, size=12, bold=False, italic=False,
                   indent=0, right_indent=0, align='left'):
        font = self._font(bold, italic)
        max_width = PAGE_W - 2 * MARGIN - indent - right_indent
        for line in _wrap_line(text, size, max_width):
            lh = size * 1.35
            self._check_space(lh)
            esc = _escape_pdf_text(line)
            w = _text_width(line, size)
            if align == 'center':
                x = MARGIN + indent + (max_width - w) / 2
            elif align == 'right':
                x = MARGIN + indent + (max_width - w)
            else:
                x = MARGIN + indent
            self._current.append(
                f'BT /{font} {size} Tf {x:.2f} {self._y:.2f} Td ({esc}) Tj ET'
            )
            self._y -= lh

    def blank(self, height=10):
        self._y -= height
        self._check_space(0)

    def _add_object(self, num, content):
        self._offsets[num] = self._buffer.tell()
        self._buffer.write(f'{num} 0 obj\n'.encode('ascii'))
        if isinstance(content, str):
            content = content.encode('latin-1', 'replace')
        self._buffer.write(content)
        self._buffer.write(b'\nendobj\n')

    def render(self, title=''):
        self._flush_page()
        if not self._pages:
            self._pages = [[]]
        n = len(self._pages)
        first = 7
        page_objs = [first + i * 2 for i in range(n)]
        content_objs = [p + 1 for p in page_objs]

        self._add_object(1, '<< /Type /Catalog /Pages 2 0 R >>')
        kids = ' '.join(f'{p} 0 R' for p in page_objs)
        self._add_object(2, f'<< /Type /Pages /Kids [{kids}] /Count {n} >>')
        self._add_object(3, '<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>')
        self._add_object(4, '<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>')
        self._add_object(5, '<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic /Encoding /WinAnsiEncoding >>')
        self._add_object(6, '<< /Type /Font /Subtype /Type1 /BaseFont /Times-BoldItalic /Encoding /WinAnsiEncoding >>')

        for page_num, content_num, lines in zip(page_objs, content_objs, self._pages):
            self._add_object(page_num, (
                f'<< /Type /Page /Parent 2 0 R '
                f'/MediaBox [0 0 {PAGE_W:.2f} {PAGE_H:.2f}] '
                f'/Contents {content_num} 0 R '
                f'/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> >> >>'
            ))
            stream = '\n'.join(lines).encode('latin-1', 'replace')
            self._add_object(
                content_num,
                b'<< /Length ' + str(len(stream)).encode('ascii')
                + b' >>\nstream\n' + stream + b'\nendstream'
            )

        total = first + n * 2
        xref = self._buffer.tell()
        self._buffer.write(f'xref\n0 {total}\n'.encode('ascii'))
        self._buffer.write(b'0000000000 65535 f \n')
        for i in range(1, total):
            self._buffer.write(f'{self._offsets[i]:010d} 00000 n \n'.encode('ascii'))
        safe_title = _escape_pdf_text(title or '')
        self._buffer.write((
            f'trailer\n<< /Size {total} /Root 1 0 R '
            f'/Info << /Title ({safe_title}) /Producer (GuionStudio) >> >>\n'
            f'startxref\n{xref}\n%%EOF\n'
        ).encode('latin-1', 'replace'))
        return self._buffer.getvalue()


def build_script_pdf(text, title='Guion'):
    """Devuelve los bytes del PDF maquetado como guion."""
    doc = _PDFDocument()
    if title:
        doc.write_line(title, size=20, bold=True, align='center')
        doc.blank(16)

    lines = text.split('\n')
    classes = [c for _, _, c in classify(text)]
    style = {
        'ACT':          dict(size=16, bold=True, align='center'),
        'SEQ':          dict(size=14, bold=True, align='center'),
        'SCENE':        dict(size=12, bold=True),
        'CHARACTER':    dict(size=12, bold=True, indent=180),
        'PARENTHETICAL':dict(size=12, italic=True, indent=144, right_indent=72),
        'DIALOGUE':     dict(size=12, indent=108, right_indent=72),
        'TRANSITION':   dict(size=12, bold=True, align='right'),
        'ACTION':       dict(size=12),
    }
    for line, cls in zip(lines, classes):
        stripped = line.strip()
        if not stripped:
            doc.blank(10)
            continue
        doc.write_line(stripped, **style.get(cls, style['ACTION']))
        if cls in ('SCENE', 'CHARACTER', 'ACT', 'SEQ'):
            doc.blank(4)
    return doc.render(title)


def write_script_pdf(path, text, title='Guion'):
    """Escritura atómica (temporal + renombrado)."""
    import os, tempfile
    data = build_script_pdf(text, title)
    path = os.path.realpath(path)
    directory = os.path.dirname(path) or '.'
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix='.guion-', suffix='.tmp')
        with os.fdopen(fd, 'wb') as fh:
            fh.write(data); fh.flush(); os.fsync(fh.fileno())
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
        return
    except OSError:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except OSError: pass
    with open(path, 'wb') as fh:
        fh.write(data)
