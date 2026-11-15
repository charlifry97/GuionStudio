# script_page.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from gi.repository import Gtk, Adw, Gio
from .editor import ScriptEditor
from .structure_panel import StructurePanel
from .story_workspace import StoryWorkspace
from .project_io import read_project, write_project, safe_file_stem, STORY_KEYS


class ScriptPage(Adw.Bin):
    """Un proyecto (documento) dentro de una pestaña.

    Contiene dos espacios de trabajo con la misma disposición: el **guion**
    (estructura + editor) y la **historia** (fichas + editor).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_file = None
        self.imported_from = None
        self.project_title = ''
        self.story_sections = {key: '' for key in STORY_KEYS}
        self._modified = False
        self.tab_page = None
        self.on_state_changed = None   # la ventana actualiza su título
        self.on_view_changed = None    # la ventana sincroniza botones/acciones
        self.on_export_story = None    # la ventana gestiona «Guardar en Word»

        self.toast_overlay = Adw.ToastOverlay()

        # ── Espacio de trabajo: guion ──
        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_position(260)
        split.set_resize_start_child(False)
        split.set_shrink_start_child(False)

        self.sidebar_box = Gtk.Box()
        self.sidebar_box.set_size_request(260, -1)
        self.structure_panel = StructurePanel()
        self.structure_panel.set_vexpand(True)
        self.structure_panel.set_hexpand(True)
        self.structure_panel.on_scene_activate = self._on_scene_activate
        self.structure_panel.on_character_activate = self._on_character_activate
        self.structure_panel.on_location_activate = self._on_location_activate
        self.sidebar_box.append(self.structure_panel)
        split.set_start_child(self.sidebar_box)

        self.editor = ScriptEditor()
        self.structure_panel.on_move_outline_item = self.editor.move_outline_item
        self.editor.on_outline_changed = self._on_outline_changed
        self.editor.on_user_changed = self._mark_modified
        self.editor.on_memory_changed = self._on_memory_changed
        self.editor.on_notice = self.toast
        split.set_end_child(self.editor)
        self.script_split = split

        # ── Espacio de trabajo: historia ──
        self.story = StoryWorkspace(on_changed=self._on_story_changed)
        self.story.on_export = lambda: self.on_export_story and self.on_export_story(self)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(120)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.stack.add_named(split, 'script')
        self.stack.add_named(self.story, 'story')
        self.stack.set_visible_child_name('script')

        self.toast_overlay.set_child(self.stack)
        self.set_child(self.toast_overlay)

        # Estados vacíos visibles desde el primer momento (antes, Personajes y
        # Locaciones aparecían en blanco hasta que se escribía algo).
        self.structure_panel.set_outline([])
        self.structure_panel.set_escaleta('', [])
        self.structure_panel.set_characters([])
        self.structure_panel.set_locations([])

    # ───────────────────────── vistas ─────────────────────────

    @property
    def view_name(self):
        return self.stack.get_visible_child_name() or 'script'

    def show_view(self, name, focus=True):
        if name not in ('script', 'story'):
            return
        changed = name != self.view_name
        self.stack.set_visible_child_name(name)
        if focus:
            self.focus_active_view()
        if changed and self.on_view_changed:
            self.on_view_changed()

    def focus_active_view(self):
        if self.view_name == 'story':
            self.story.focus_editor()
        else:
            self.editor.view.grab_focus()

    def set_sidebar_visible(self, visible):
        self.sidebar_box.set_visible(visible)
        self.story.set_sidebar_visible(visible)

    # ───────────────────────── callbacks ─────────────────────────

    def _on_scene_activate(self, line_num):
        self.editor.scroll_to_line(line_num)

    def _on_outline_changed(self, outline, text=None):
        if text is None:
            text = self.editor.get_text()
        self.structure_panel.set_outline(outline)
        self.structure_panel.set_escaleta(text, outline)

    def _on_character_activate(self, name):
        self.editor.find_and_jump(name)

    def _on_location_activate(self, name):
        self.editor.find_and_jump(name)

    def _on_memory_changed(self, characters, locations):
        self.structure_panel.set_characters(characters)
        self.structure_panel.set_locations(locations)

    def _on_story_changed(self, key, text):
        self.story_sections[key] = text
        self._mark_modified()

    def _mark_modified(self):
        self._modified = True
        self._update_tab_state()

    # ───────────────────────── título / estado ─────────────────────────

    def set_project_title(self, title):
        title = (title or '').strip()
        if title == self.project_title:
            return
        self.project_title = title
        self._mark_modified()

    def get_display_title(self):
        if self.project_title:
            return self.project_title
        if self.current_file:
            return os.path.basename(self.current_file)
        if self.imported_from:
            return os.path.splitext(os.path.basename(self.imported_from))[0]
        return "Sin título"

    def suggested_file_name(self):
        if self.current_file:
            return os.path.basename(self.current_file)
        stem = safe_file_stem(self.project_title)
        if stem:
            return stem + '.guion'
        if self.imported_from:
            return os.path.splitext(os.path.basename(self.imported_from))[0] + '.guion'
        return 'Sin título.guion'

    def _update_tab_state(self):
        if self.tab_page:
            self.tab_page.set_title(self.get_display_title())
            if self._modified:
                self.tab_page.set_indicator_icon(Gio.ThemedIcon.new('media-record-symbolic'))
                self.tab_page.set_indicator_tooltip("Modificado")
            else:
                self.tab_page.set_indicator_icon(None)
                self.tab_page.set_indicator_tooltip("")
        if self.on_state_changed:
            self.on_state_changed()

    # ───────────────────────── contenido ─────────────────────────

    def get_text(self):
        return self.editor.get_text()

    def set_text(self, text):
        self.editor.set_text(text)
        self._modified = False
        self._update_tab_state()

    def load_from(self, path):
        """Carga un archivo. Lanza OSError/ValueError si no se puede leer.

        Un proyecto .guion queda asociado a su archivo. Cualquier otro
        formato (.txt, .fountain…) se importa como documento nuevo para que
        «Guardar» nunca lo sobrescriba con el formato de proyecto.
        """
        data = read_project(path)
        self.project_title = data['title']
        self.story_sections = {key: '' for key in STORY_KEYS}
        self.story_sections.update(data['story_sections'])
        self.editor.set_text(data['content'])
        self.editor.import_highlights(data['highlights'])
        self.story.set_sections(self.story_sections)
        if data['is_project']:
            self.current_file = path
            self.imported_from = None
        else:
            self.current_file = None
            self.imported_from = path
        self._modified = False
        self._update_tab_state()
        return data['notice']

    def save_to(self, path):
        # Leer el estado actual de los widgets en lugar del diccionario en
        # memoria: así se guarda siempre lo que el usuario ve en pantalla,
        # aunque _on_story_changed no se haya disparado por cualquier motivo.
        self.story_sections = self.story.get_sections()
        data = {
            'version': 1,
            'application': 'GuionStudio',
            'title': self.project_title,
            'content': self.get_text(),
            'story_sections': dict(self.story_sections),
            'highlights': self.editor.export_highlights(),
        }
        write_project(path, data)
        self.current_file = path
        self.imported_from = None
        self._modified = False
        self._update_tab_state()

    def story_export_sections(self):
        """Fichas con contenido, en orden, para exportar: [(nombre, texto)]."""
        current = self.story.get_sections()
        return [(key, current.get(key, '')) for key in STORY_KEYS
                if current.get(key, '').strip()]

    def toast(self, msg):
        self.toast_overlay.add_toast(Adw.Toast.new(msg))
