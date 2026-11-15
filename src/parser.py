# parser.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Parser Fountain-lite + extracción de memoria de la historia."""
import re

SCENE_RE = re.compile(r'^(INT\.|EXT\.|INT/EXT\.?|I/E\.?|EST\.)\s', re.IGNORECASE)
ACT_RE = re.compile(r'^#\s*(?:ACTO?)\s*\d*\s*[-:.]?\s*(.*)$', re.IGNORECASE)
SEQ_RE = re.compile(r'^##\s*(?:SECUENCIA|SEQUENCE|SEQ)\.?\s*\d*\s*[-:.]?\s*(.*)$', re.IGNORECASE)
PAREN_RE = re.compile(r'^\(.*\)$')
TRANS_END = re.compile(r'^[A-ZÁÉÍÓÚÜÑ\s]+TO:$')
TRANS_WORDS = re.compile(
    r'^(FADE IN|FADE OUT|CORTE A|FUNDIDO A NEGRO|SMASH CUT TO|FUNDIDO)[:.]?$',
    re.IGNORECASE,
)
SCENE_LOC_RE = re.compile(
    r'^(INT\.|EXT\.|INT/EXT\.?|I/E\.?|EST\.)\s+(.+?)(?:\s+-\s+.*)?$',
    re.IGNORECASE,
)
CHAR_NAME_RE = re.compile(r'^([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s\.\'\-]+)')


def is_transition(s: str) -> bool:
    if s.startswith('>'):
        return True
    if TRANS_END.match(s):
        return True
    if TRANS_WORDS.match(s.strip()):
        return True
    return False


def looks_like_character_cue(line: str) -> bool:
    """Reconoce nombres breves en formato de encabezado, incluso antes de
    que el usuario los haya convertido a mayúsculas.

    Se exige que cada palabra parezca un nombre propio y que no haya
    puntuación de cierre propia de una oración para evitar convertir acciones.
    """
    value = line.strip()
    if not value or len(value) > 40 or value.endswith(('.', '!', '?', ':', ';', ',')):
        return False
    words = value.split()
    if not 1 <= len(words) <= 4:
        return False
    return all(word[:1].isupper() and word[1:].islower()
               for word in words if any(ch.isalpha() for ch in word)) and all(
                   any(ch.isalpha() for ch in word) for word in words)


def is_character(s: str) -> bool:
    if not s or not any(c.isalpha() for c in s):
        return False
    if len(s) > 50 or s.endswith(':'):
        return False
    return s == s.upper() or looks_like_character_cue(s)


def normalize_structural_case(text: str) -> str:
    """Normaliza solo encabezados y rótulos del guion, nunca acción o diálogo."""
    lines = text.split('\n')
    for index, line in enumerate(lines):
        stripped = line.strip()
        if ACT_RE.match(stripped) or SEQ_RE.match(stripped) or SCENE_RE.match(stripped):
            leading = line[:len(line) - len(line.lstrip())]
            trailing = line[len(line.rstrip()):]
            lines[index] = leading + stripped.upper() + trailing
            continue
        if is_transition(stripped):
            leading = line[:len(line) - len(line.lstrip())]
            trailing = line[len(line.rstrip()):]
            lines[index] = leading + stripped.upper() + trailing
            continue
        # Un rótulo de personaje se reconoce por su posición y forma nominal.
        if (index == 0 or not lines[index - 1].strip()) and looks_like_character_cue(stripped):
            next_line = ''
            for follow in range(index + 1, len(lines)):
                if lines[follow].strip():
                    next_line = lines[follow].strip()
                    break
            if next_line and (next_line.startswith('(') or not looks_like_character_cue(next_line)):
                leading = line[:len(line) - len(line.lstrip())]
                trailing = line[len(line.rstrip()):]
                lines[index] = leading + stripped.upper() + trailing
    return '\n'.join(lines)


def classify(text: str):
    lines = text.split('\n')
    result = []
    offset = 0
    in_dialogue = False
    for i, line in enumerate(lines):
        s = line.strip()
        prev_blank = (i == 0) or (lines[i - 1].strip() == '')
        cls = 'ACTION'
        if ACT_RE.match(s):
            cls, in_dialogue = 'ACT', False
        elif SEQ_RE.match(s):
            cls, in_dialogue = 'SEQ', False
        elif SCENE_RE.match(s):
            cls, in_dialogue = 'SCENE', False
        elif not s:
            cls, in_dialogue = 'BLANK', False
        elif in_dialogue:
            cls = 'PARENTHETICAL' if PAREN_RE.match(s) else 'DIALOGUE'
        elif prev_blank and is_transition(s):
            cls = 'TRANSITION'
        elif prev_blank and is_character(s):
            cls, in_dialogue = 'CHARACTER', True
        result.append((offset, offset + len(line), cls))
        offset += len(line) + 1
    return result


def extract_outline(text: str, classified=None):
    outline = []
    line_no = 1
    last_offset = 0
    for start, end, cls in (classified if classified is not None else classify(text)):
        if cls in ('ACT', 'SEQ', 'SCENE'):
            line_no += text.count('\n', last_offset, start)
            last_offset = start
            outline.append({
                'type': cls,
                'offset': start,
                'line': line_no,
                'text': text[start:end].strip(),
            })
    return outline


def extract_characters(text: str, classified=None):
    """Nombres de personajes encontrados en líneas CHARACTER."""
    chars = []
    seen = set()
    for start, end, cls in (classified if classified is not None else classify(text)):
        if cls == 'CHARACTER':
            line = text[start:end].strip()
            m = CHAR_NAME_RE.match(line)
            if m:
                name = m.group(1).strip()
                if name and name not in seen:
                    seen.add(name)
                    chars.append(name)
    return chars


def extract_locations(text: str, classified=None):
    """Locaciones encontradas en encabezados de escena."""
    locs = []
    seen = set()
    for start, end, cls in (classified if classified is not None else classify(text)):
        if cls == 'SCENE':
            line = text[start:end].strip()
            m = SCENE_LOC_RE.match(line)
            if m:
                loc = m.group(2).strip()
                if loc and loc not in seen:
                    seen.add(loc)
                    locs.append(loc)
    return locs


def word_count(text: str) -> int:
    return len(re.findall(r'\b\w+\b', text))


def page_estimate(text: str) -> float:
    return max(1.0, round((text.count('\n') + 1) / 55, 1))


_LEVELS = {'ACT': 0, 'SEQ': 1, 'SCENE': 2}


def _outline_parents(outline):
    """Padre lógico de cada hito (acto > secuencia > escena)."""
    parents = []
    stack = []
    for index, item in enumerate(outline):
        kind = item['type']
        level = _LEVELS.get(kind)
        if level is None:
            parents.append(None)
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        if kind == 'ACT':
            parent = None
        elif kind == 'SEQ':
            parent = next(((t, i) for l, t, i in reversed(stack)
                           if t == 'ACT'), None)
        else:
            parent = next(((t, i) for l, t, i in reversed(stack)
                           if t == 'SEQ'), None)
            if parent is None:
                parent = next(((t, i) for l, t, i in reversed(stack)
                               if t == 'ACT'), None)
        parents.append(parent)
        stack.append((level, kind, index))
    return parents


def outline_move_flags(outline):
    """Para cada hito devuelve (puede_subir, puede_bajar) en O(n)."""
    parents = _outline_parents(outline)
    groups = {}
    for index, item in enumerate(outline):
        groups.setdefault((item['type'], parents[index]), []).append(index)
    flags = [(False, False)] * len(outline)
    for members in groups.values():
        for position, index in enumerate(members):
            flags[index] = (position > 0, position < len(members) - 1)
    return flags


def move_outline_spans(text: str, outline, item_index: int, direction: int):
    """Calcula (a_ini, a_fin, b_ini, b_fin) de los dos bloques hermanos que
    se intercambian, o None si el movimiento no es posible."""
    if direction not in (-1, 1) or not (0 <= item_index < len(outline)):
        return None
    parents = _outline_parents(outline)
    current = outline[item_index]
    siblings = [i for i, item in enumerate(outline)
                if item['type'] == current['type'] and parents[i] == parents[item_index]]
    target_position = siblings.index(item_index) + direction
    if not (0 <= target_position < len(siblings)):
        return None

    other_index = siblings[target_position]
    first_index, second_index = sorted((item_index, other_index))

    def block_end(index):
        level = _LEVELS[outline[index]['type']]
        for j in range(index + 1, len(outline)):
            if _LEVELS[outline[j]['type']] <= level:
                return outline[j]['offset']
        return len(text)

    first_start = outline[first_index]['offset']
    second_start = outline[second_index]['offset']
    first_end = block_end(first_index)
    second_end = block_end(second_index)
    if first_end != second_start or second_end < second_start:
        return None
    return first_start, first_end, second_start, second_end


def move_outline_block(text: str, outline, item_index: int, direction: int):
    """Devuelve el guion con un hito intercambiado con su hermano inmediato.

    El bloque incluye todo el texto hasta el siguiente hito del mismo nivel
    o de un nivel superior. Nunca mueve una escena fuera de su secuencia/acto,
    ni una secuencia fuera de su acto.
    """
    spans = move_outline_spans(text, outline, item_index, direction)
    if spans is None:
        return None
    first_start, first_end, second_start, second_end = spans
    return (text[:first_start] + text[second_start:second_end]
            + text[first_start:first_end] + text[second_end:])


def remap_ranges_after_swap(ranges, spans):
    """Reubica rangos (ini, fin) tras intercambiar dos bloques contiguos.

    Los rangos que cruzan el límite entre bloques se recortan por bloque.
    """
    a0, a1, b0, b1 = spans
    len_a, len_b = a1 - a0, b1 - b0
    result = []
    for start, end in ranges:
        if end <= a0 or start >= b1:
            result.append((start, end))
            continue
        pieces = (
            (max(start, a0), min(end, a1), len_b),     # bloque A pasa detrás de B
            (max(start, b0), min(end, b1), -len_a),    # bloque B pasa delante de A
        )
        for lo, hi, delta in pieces:
            if hi > lo:
                result.append((lo + delta, hi + delta))
    return result


_FIND_CACHE = {}


def find_occurrence(text: str, needle: str, start: int = 0):
    """Busca `needle` como palabra completa, sin distinguir mayúsculas, a
    partir de `start` y dando la vuelta al llegar al final.

    Devuelve (posición, longitud) o None.
    """
    needle = needle.strip()
    if not needle:
        return None
    pattern = _FIND_CACHE.get(needle)
    if pattern is None:
        if len(_FIND_CACHE) > 64:
            _FIND_CACHE.clear()
        pattern = re.compile(r'(?<!\w)' + re.escape(needle) + r'(?!\w)', re.IGNORECASE)
        _FIND_CACHE[needle] = pattern
    match = pattern.search(text, max(0, start)) or pattern.search(text, 0)
    if not match:
        return None
    return match.start(), match.end() - match.start()
