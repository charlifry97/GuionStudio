# story_memory.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Memoria de la historia: personajes, locaciones y estructura."""

from .parser import classify, extract_characters, extract_locations, extract_outline


class StoryMemory:
    def __init__(self):
        self.characters = []
        self.locations = []
        self.outline = []

    def update_from_text(self, text, classified=None):
        """Reescanea el texto y actualiza las listas. Devuelve True si algo cambió.

        `classified` permite reutilizar una clasificación ya calculada.
        """
        if classified is None:
            classified = classify(text)
        new_chars = extract_characters(text, classified)
        new_locs = extract_locations(text, classified)
        new_outline = extract_outline(text, classified)

        changed = False
        if new_chars != self.characters:
            self.characters = new_chars
            changed = True
        if new_locs != self.locations:
            self.locations = new_locs
            changed = True
        # El esquema incluye offsets y números de línea, que cambian con casi
        # cada pulsación; no cuenta como cambio de la memoria (personajes y
        # locaciones), o las listas laterales se reconstruirían sin parar.
        self.outline = new_outline
        return changed

    def suggestions(self, prefix, exclude_word=None, limit=20):
        """Devuelve sugerencias para un prefijo dado."""
        if not prefix:
            return []
        pl = prefix.lower()
        ex = (exclude_word or '').lower()
        results = []
        for name in self.characters:
            if name.lower() == ex:
                continue
            if name.lower().startswith(pl):
                results.append({'kind': 'character', 'name': name, 'icon': '👤'})
        for name in self.locations:
            if name.lower() == ex:
                continue
            if name.lower().startswith(pl):
                results.append({'kind': 'location', 'name': name, 'icon': '📍'})
        results.sort(key=lambda x: (x['kind'] != 'character', x['name']))
        return results[:limit]
