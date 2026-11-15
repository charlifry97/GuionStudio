# exporter.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Exportadores: HTML, TXT, Fountain, RTF (Word)."""
import html
from .parser import classify


def export_fountain(text: str) -> str:
    return text


def export_txt(text: str) -> str:
    return text


def _rtf_escape(s: str) -> str:
    out = []
    for ch in s:
        if ch == '\\':
            out.append('\\\\')
        elif ch == '{':
            out.append('\\{')
        elif ch == '}':
            out.append('\\}')
        elif ord(ch) > 127:
            out.append(f'\\u{ord(ch)}?')
        else:
            out.append(ch)
    return ''.join(out)


def export_rtf(text: str) -> str:
    lines = text.split('\n')
    classes = [c for _, _, c in classify(text)]

    parts = [
        r'{\rtf1\ansi\deff0',
        r'{\fonttbl{\f0\fmodern Courier New;}}',
        r'\f0\fs24',
    ]

    for line, cls in zip(lines, classes):
        esc = _rtf_escape(line)
        if cls == 'ACT':
            parts.append(r'\pard\qc\b\fs32 ' + esc + r'\par\pard\fs24')
        elif cls == 'SEQ':
            parts.append(r'\pard\b\fs28 ' + esc + r'\par\pard\fs24')
        elif cls == 'SCENE':
            parts.append(r'\pard\li2160\b ' + esc + r'\par\pard\fs24')
        elif cls == 'CHARACTER':
            parts.append(r'\pard\li3600\b ' + esc + r'\par\pard\fs24')
        elif cls == 'PARENTHETICAL':
            parts.append(r'\pard\li2880\ri1440\i ' + esc + r'\par\pard\fs24')
        elif cls == 'DIALOGUE':
            parts.append(r'\pard\li2160\ri1440 ' + esc + r'\par\pard\fs24')
        elif cls == 'TRANSITION':
            parts.append(r'\pard\qr\b ' + esc + r'\par\pard\fs24')
        elif cls == 'BLANK':
            parts.append(r'\par')
        else:
            parts.append(r'\pard\li2160 ' + esc + r'\par\pard\fs24')

    parts.append('}')
    return '\n'.join(parts)


def export_html(text: str, title: str = "Guion") -> str:
    lines = text.split('\n')
    classes = [c for _, _, c in classify(text)]
    css = """
    body { font-family: "Courier New", monospace; max-width: 8.5in;
           margin: 1in auto; padding: 0 1in; line-height: 1.4; }
    .scene { font-weight: bold; text-transform: uppercase; margin-top: 1.5em; }
    .character { margin-left: 2.5in; font-weight: bold;
                 text-transform: uppercase; margin-top: 1em; }
    .dialogue { margin-left: 1.5in; margin-right: 1.5in; }
    .parenthetical { margin-left: 2in; font-style: italic; }
    .transition { text-align: right; text-transform: uppercase; margin-top: 1em; }
    .act { font-size: 1.5em; font-weight: bold; margin: 2em 0 1em;
           text-align: center; border-bottom: 2px solid #333; padding-bottom: .3em; }
    .seq { font-size: 1.2em; font-weight: bold; margin: 1.5em 0 1em; }
    .action { margin: 1em 0; }
    .blank { height: .5em; }
    """
    out = [
        '<!DOCTYPE html>',
        '<html lang="es"><head><meta charset="utf-8">',
        f'<title>{html.escape(title)}</title>',
        f'<style>{css}</style></head><body>',
    ]
    mapping = {
        'ACT': 'act', 'SEQ': 'seq', 'SCENE': 'scene',
        'CHARACTER': 'character', 'DIALOGUE': 'dialogue',
        'PARENTHETICAL': 'parenthetical', 'TRANSITION': 'transition',
        'ACTION': 'action', 'BLANK': 'blank',
    }
    for line, cls in zip(lines, classes):
        out.append(f'<div class="{mapping.get(cls, "action")}">{html.escape(line)}</div>')
    out.append('</body></html>')
    return '\n'.join(out)
    
