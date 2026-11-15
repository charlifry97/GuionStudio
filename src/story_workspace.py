# story_workspace.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Espacio de trabajo de la historia.

Tiene la misma disposición que el del guion: panel lateral con las fichas,
un área amplia de escritura con los mismos márgenes y una barra de
contadores en la parte inferior. Cada ficha conserva su propio historial
de deshacer/rehacer.
"""

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from .parser import word_count


STORY_SECTIONS = (
    ('Argumento', '📚',
     'Desarrollo narrativo completo: acontecimientos, causalidad y evolución.'),
    ('Sinopsis', '📖',
     'Resumen de la historia, sus personajes y su conflicto principal.'),
    ('Storyline', '🧭',
     'La historia condensada en una línea narrativa.'),
    ('Logline', '🎬',
     'Protagonista + objetivo + conflicto + elemento diferencial.'),
)


class StoryWorkspace(Gtk.Box):
    def __init__(self, on_changed=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_changed = on_changed          # callback(clave, texto)
        self.on_export = None                 # callback() → guardar en Word
        self._loading = False
        self._selecting = False
        self._buffers = {}
        self._count_labels = {}
        self._rows = {}
        self._current = STORY_SECTIONS[0][0]
        self._meta = {key: (emoji, hint) for key, emoji, hint in STORY_SECTIONS}

        for key, _emoji, _hint in STORY_SECTIONS:
            buf = Gtk.TextBuffer()
            buf.connect('changed', self._on_buffer_changed, key)
            self._buffers[key] = buf

        self.split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.split.set_vexpand(True)
        self.split.set_hexpand(True)
        self.split.set_position(260)
        self.split.set_resize_start_child(False)
        self.split.set_shrink_start_child(False)
        self.split.set_shrink_end_child(False)
        self.split.set_start_child(self._build_sidebar())
        self.split.set_end_child(self._build_editor_area())
        self.append(self.split)

        self.select_section(self._current)

    # ───────────────────────── construcción ─────────────────────────

    def _build_sidebar(self):
        self.sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sidebar_box.set_size_request(260, -1)

        title = Gtk.Label(label='📝 Desarrollo de la historia', xalign=0)
        title.add_css_class('heading')
        title.set_margin_top(14)
        title.set_margin_bottom(8)
        title.set_margin_start(12)
        title.set_margin_end(12)
        title.set_wrap(True)
        self.sidebar_box.append(title)

        self.section_list = Gtk.ListBox()
        self.section_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.section_list.add_css_class('navigation-sidebar')
        self.section_list.connect('row-selected', self._on_row_selected)

        for key, emoji, _hint in STORY_SECTIONS:
            row = Gtk.ListBoxRow()
            row.section_key = key
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_top(7)
            box.set_margin_bottom(7)
            box.set_margin_start(8)
            box.set_margin_end(8)
            glyph = Gtk.Label(label=emoji)
            glyph.add_css_class('emoji-glyph')
            box.append(glyph)
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            info.set_hexpand(True)
            name = Gtk.Label(label=key, xalign=0)
            name.add_css_class('heading')
            count = Gtk.Label(label='Vacío', xalign=0)
            count.add_css_class('caption')
            count.add_css_class('dim-label')
            info.append(name)
            info.append(count)
            box.append(info)
            row.set_child(box)
            self.section_list.append(row)
            self._rows[key] = row
            self._count_labels[key] = count

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.section_list)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.sidebar_box.append(scroll)

        self.total_label = Gtk.Label(label='', xalign=0, wrap=True)
        self.total_label.add_css_class('caption')
        self.total_label.add_css_class('dim-label')
        self.total_label.set_margin_start(12)
        self.total_label.set_margin_end(12)
        self.total_label.set_margin_top(8)
        self.total_label.set_margin_bottom(10)
        self.sidebar_box.append(self.total_label)

        export_btn = Gtk.Button(label='📄 Guardar en Word…')
        export_btn.set_tooltip_text('Exporta las cuatro fichas a un documento .docx (Ctrl+Mayús+E)')
        export_btn.set_margin_start(12)
        export_btn.set_margin_end(12)
        export_btn.set_margin_bottom(14)
        export_btn.connect('clicked', lambda *_: self.on_export and self.on_export())
        self.sidebar_box.append(export_btn)
        return self.sidebar_box

    def _build_editor_area(self):
        area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        area.set_hexpand(True)
        area.set_vexpand(True)

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        header.set_margin_top(18)
        header.set_margin_bottom(6)
        header.set_margin_start(96)
        header.set_margin_end(96)
        self.title_label = Gtk.Label(label='', xalign=0)
        self.title_label.add_css_class('title-2')
        self.hint_label = Gtk.Label(label='', xalign=0, wrap=True)
        self.hint_label.add_css_class('dim-label')
        header.append(self.title_label)
        header.append(self.hint_label)
        area.append(header)

        self.view = Gtk.TextView()
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        # Mismos márgenes que el editor del guion para que ambos espacios
        # se sientan como una sola herramienta.
        self.view.set_left_margin(96)
        self.view.set_right_margin(96)
        self.view.set_top_margin(24)
        self.view.set_bottom_margin(48)
        self.view.set_pixels_below_lines(6)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.view)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        area.append(scrolled)

        self.status = Gtk.Label(label='')
        self.status.add_css_class('dim-label')
        self.status.set_margin_top(6)
        self.status.set_margin_bottom(6)
        area.append(self.status)
        return area

    # ───────────────────────── datos ─────────────────────────

    @staticmethod
    def _text_of(buf):
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)

    def set_sections(self, sections):
        """Carga el contenido de las fichas sin marcar el documento como modificado."""
        self._loading = True
        try:
            for key, buf in self._buffers.items():
                value = sections.get(key, '') if isinstance(sections, dict) else ''
                buf.begin_irreversible_action()
                buf.set_text(value if isinstance(value, str) else '')
                buf.end_irreversible_action()
        finally:
            self._loading = False
        self._refresh_all_counts()

    def get_sections(self):
        return {key: self._text_of(buf) for key, buf in self._buffers.items()}

    def _on_buffer_changed(self, buf, key):
        self._refresh_counts(key)
        if self._loading:
            return
        if self.on_changed:
            self.on_changed(key, self._text_of(buf))

    # ───────────────────────── contadores ─────────────────────────

    def _refresh_counts(self, key):
        text = self._text_of(self._buffers[key])
        words = word_count(text)
        self._count_labels[key].set_text(
            'Vacío' if not text.strip() else f'{words} palabras')
        if key == self._current:
            self._update_status(text, words)
        total = sum(word_count(self._text_of(b)) for b in self._buffers.values())
        self.total_label.set_text(f'Total: {total} palabras en las cuatro fichas')

    def _refresh_all_counts(self):
        for key in self._buffers:
            self._refresh_counts(key)

    def _update_status(self, text, words):
        paragraphs = sum(1 for block in text.split('\n') if block.strip())
        self.status.set_text(
            f'{words} palabras · {paragraphs} párrafos · {len(text)} caracteres')

    # ───────────────────────── navegación ─────────────────────────

    def _on_row_selected(self, _listbox, row):
        if self._selecting or row is None or not hasattr(row, 'section_key'):
            return
        self._show_section(row.section_key)

    def select_section(self, key):
        if key not in self._buffers:
            return
        self._selecting = True
        try:
            self.section_list.select_row(self._rows[key])
        finally:
            self._selecting = False
        self._show_section(key)

    def _show_section(self, key):
        self._current = key
        emoji, hint = self._meta[key]
        self.title_label.set_text(f'{emoji} {key}')
        self.hint_label.set_text(hint)
        self.view.set_buffer(self._buffers[key])
        text = self._text_of(self._buffers[key])
        self._update_status(text, word_count(text))

    def focus_editor(self):
        self.view.grab_focus()

    def set_sidebar_visible(self, visible):
        self.sidebar_box.set_visible(visible)
