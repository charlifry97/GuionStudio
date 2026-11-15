# project_io.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Lectura/escritura de proyectos .guion y lista de proyectos recientes.

No depende de GTK, de modo que puede probarse de forma aislada.
"""

import json
import os
import re
import stat
import tempfile

PROJECT_EXTENSIONS = ('.guion', '.json')
STORY_KEYS = ('Argumento', 'Sinopsis', 'Storyline', 'Logline')
MAX_RECENT = 8


def read_project(path):
    """Lee un archivo y devuelve un diccionario con su contenido.

    Claves: content, story_sections, highlights, is_project, notice.

    * ``is_project`` es True solo si el archivo era un proyecto .guion/.json
      válido. En cualquier otro caso (texto, Fountain, JSON dañado) el
      contenido se importa como texto y el documento NO queda asociado al
      archivo original, para que «Guardar» nunca sobrescriba un .txt o
      .fountain con JSON.
    * Lanza OSError / ValueError (incluye UnicodeDecodeError) si no se puede leer.
    """
    with open(path, 'r', encoding='utf-8') as handle:
        raw = handle.read()

    result = {
        'content': raw,
        'story_sections': {},
        'highlights': {},
        'is_project': False,
        'notice': '',
        'title': '',
    }
    if os.path.splitext(path)[1].lower() not in PROJECT_EXTENSIONS:
        return result

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        result['notice'] = ('El archivo no tiene formato de proyecto; '
                            'se abrió como texto sin modificar el original.')
        return result
    if not isinstance(payload, dict) or not isinstance(payload.get('content', ''), str):
        result['notice'] = ('El archivo no tiene formato de proyecto; '
                            'se abrió como texto sin modificar el original.')
        return result

    sections = payload.get('story_sections', {})
    if isinstance(sections, dict):
        result['story_sections'] = {
            key: value for key, value in sections.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    highlights = payload.get('highlights', {})
    result['highlights'] = highlights if isinstance(highlights, dict) else {}
    result['content'] = payload.get('content', '')
    title = payload.get('title', '')
    result['title'] = title.strip() if isinstance(title, str) else ''
    result['is_project'] = True
    return result


_UNSAFE_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_file_stem(title, limit=80):
    """Convierte un título en un nombre de archivo válido (sin extensión)."""
    stem = _UNSAFE_NAME.sub('', title or '')
    stem = re.sub(r'\s+', ' ', stem).strip(' .')
    return stem[:limit].rstrip(' .')


def write_project(path, payload):
    """Guarda el proyecto de forma atómica.

    Escribe en un archivo temporal contiguo y lo renombra, de modo que un
    corte o un error a mitad de escritura nunca deja el proyecto truncado.
    Si el directorio no admite archivos temporales (p. ej. algunos portales
    de Flatpak) recurre a una escritura directa.
    """
    path = os.path.realpath(path)
    directory = os.path.dirname(path) or '.'
    mode = 0o644
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        pass

    # Se serializa primero: si el contenido no es válido no se toca el disco.
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix='.guion-', suffix='.tmp')
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
        return
    except OSError:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(serialized)


# ───────────────────────── Proyectos recientes ─────────────────────────

def load_recent(recent_file):
    """Devuelve las rutas recientes que siguen existiendo (máx. MAX_RECENT)."""
    try:
        with open(recent_file, 'r', encoding='utf-8') as handle:
            entries = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(entries, list):
        return []
    seen = []
    for item in entries:
        if isinstance(item, str) and item not in seen and os.path.isfile(item):
            seen.append(item)
    return seen[:MAX_RECENT]


def _save_recent(recent_file, entries):
    try:
        os.makedirs(os.path.dirname(recent_file), exist_ok=True)
        with open(recent_file, 'w', encoding='utf-8') as handle:
            json.dump(entries[:MAX_RECENT], handle, ensure_ascii=False, indent=2)
    except OSError:
        pass


def add_recent(recent_file, path):
    """Pone `path` al principio de la lista y devuelve la lista actualizada."""
    path = str(path)
    try:
        with open(recent_file, 'r', encoding='utf-8') as handle:
            stored = json.load(handle)
        stored = [i for i in stored if isinstance(i, str)] if isinstance(stored, list) else []
    except (OSError, ValueError):
        stored = []
    entries = [path] + [item for item in stored if item != path]
    _save_recent(recent_file, entries)
    return load_recent(recent_file)


def remove_recent(recent_file, path):
    """Quita `path` de la lista y devuelve la lista actualizada."""
    try:
        with open(recent_file, 'r', encoding='utf-8') as handle:
            stored = json.load(handle)
        stored = [i for i in stored if isinstance(i, str)] if isinstance(stored, list) else []
    except (OSError, ValueError):
        stored = []
    _save_recent(recent_file, [item for item in stored if item != str(path)])
    return load_recent(recent_file)
