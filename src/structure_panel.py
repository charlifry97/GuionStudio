# structure_panel.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Panel lateral con Estructura / Escaleta / Personajes / Locaciones."""
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

from .parser import outline_move_flags


# Emojis de cada elemento. Se usan emojis (y no iconos simbólicos) porque se
# ven igual en cualquier tema de iconos y distinguen bien cada elemento.
EMOJI_ACT = '🎭'
EMOJI_SEQ = '🎞️'
EMOJI_SCENE = '🎬'
EMOJI_CHARACTER = '👤'
EMOJI_LOCATION = '📍'

SECTIONS = (
    ('outline', '🗂️', 'Estructura'),
    ('escaleta', '📋', 'Escaleta'),
    ('characters', '👥', 'Personajes'),
    ('locations', EMOJI_LOCATION, 'Locaciones'),
)


def _emoji(glyph):
    label = Gtk.Label(label=glyph)
    label.add_css_class('emoji-glyph')
    label.set_valign(Gtk.Align.CENTER)
    return label


def _placeholder_row(text):
    label = Gtk.Label(label=text)
    label.add_css_class('dim-label')
    label.set_wrap(True)
    label.set_margin_top(24)
    label.set_margin_bottom(12)
    label.set_margin_start(12)
    label.set_margin_end(12)
    row = Gtk.ListBoxRow()
    row.set_activatable(False)
    row.set_selectable(False)
    row.set_child(label)
    return row


class StructurePanel(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_scene_activate = None
        self.on_move_outline_item = None
        self.on_character_activate = None
        self.on_location_activate = None

        # Firmas para no reconstruir listas cuando nada ha cambiado.
        self._outline_sig = None
        self._outline_rows = []
        self._escaleta_sig = None
        self._escaleta_rows = []
        self._counts = {key: 0 for key, _e, _t in SECTIONS}
        self._titles = {key: (emoji, title) for key, emoji, title in SECTIONS}

        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)

        self._build_switcher()

        # ── Estructura ──
        self.outline_list = self._make_list(self._on_outline_activated)
        self._outline_scroll = self._wrap(self.outline_list)
        self.stack.add_named(self._outline_scroll, 'outline')

        # ── Escaleta ──
        self.escaleta_list = self._make_list(self._on_escaleta_activated)
        self._escaleta_scroll = self._wrap(self.escaleta_list)
        self.stack.add_named(self._escaleta_scroll, 'escaleta')

        # ── Personajes ──
        self.chars_list = self._make_list(self._on_character_activated)
        self.stack.add_named(self._wrap(self.chars_list), 'characters')

        # ── Locaciones ──
        self.locs_list = self._make_list(self._on_location_activated)
        self.stack.add_named(self._wrap(self.locs_list), 'locations')

        self.append(self.stack)
        # Se activa al final, cuando ya existen el encabezado y las páginas.
        self._tab_buttons['outline'].set_active(True)
        self._show_section('outline')

    # ───────────────────────── utilidades ─────────────────────────

    @staticmethod
    def _make_list(on_activated):
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        listbox.set_activate_on_single_click(True)
        # row-activated se emite en cada clic (incluso sobre la fila ya
        # seleccionada), a diferencia de row-selected.
        listbox.connect('row-activated', on_activated)
        return listbox

    @staticmethod
    def _wrap(listbox):
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(listbox)
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        return scroll

    @staticmethod
    def _clear(listbox):
        while (child := listbox.get_first_child()):
            listbox.remove(child)

    @staticmethod
    def _scroll_value(scroll):
        return scroll.get_vadjustment().get_value()

    @staticmethod
    def _restore_scroll(scroll, value):
        if not value:
            return
        adjustment = scroll.get_vadjustment()

        def restore():
            adjustment.set_value(value)
            return False

        GLib.idle_add(restore)

    # ───────────────────────── selector de sección ─────────────────────────

    def _build_switcher(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.add_css_class('linked')
        bar.set_homogeneous(True)
        bar.set_margin_top(8)
        bar.set_margin_start(10)
        bar.set_margin_end(10)
        bar.set_margin_bottom(4)
        self._tab_buttons = {}
        first = None
        for key, emoji, title in SECTIONS:
            button = Gtk.ToggleButton(label=emoji)
            button.add_css_class('sidebar-tab')
            button.set_tooltip_text(title)
            button.set_hexpand(True)
            if first is None:
                first = button
            else:
                button.set_group(first)
            button.connect('toggled', self._on_tab_toggled, key)
            bar.append(button)
            self._tab_buttons[key] = button
        self.append(bar)

        self.heading = Gtk.Label(label='', xalign=0)
        self.heading.add_css_class('heading')
        self.heading.set_margin_start(14)
        self.heading.set_margin_end(14)
        self.heading.set_margin_top(6)
        self.heading.set_margin_bottom(6)
        self.append(self.heading)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    def _on_tab_toggled(self, button, key):
        if button.get_active():
            self._show_section(key)

    def _show_section(self, key):
        self.stack.set_visible_child_name(key)
        self._update_heading(key)

    def _update_heading(self, key=None):
        key = key or self.stack.get_visible_child_name() or 'outline'
        emoji, title = self._titles[key]
        count = self._counts.get(key, 0)
        self.heading.set_text(f'{emoji} {title}' + (f' · {count}' if count else ''))

    def show_section(self, key):
        """Cambia de sección desde fuera (p. ej. un atajo)."""
        if key in self._tab_buttons:
            self._tab_buttons[key].set_active(True)

    # ───────────────────────── Estructura ─────────────────────────

    def set_outline(self, outline):
        signature = [(item['type'], item['text']) for item in outline]
        if signature == self._outline_sig:
            # Misma estructura: solo pueden haber cambiado los números de
            # línea. Se actualizan en sitio para no parpadear ni perder el
            # desplazamiento al escribir.
            for row, item in zip(self._outline_rows, outline):
                row.scene_line = item['line']
            return
        self._outline_sig = signature
        self._outline_rows = []
        scroll_value = self._scroll_value(self._outline_scroll)
        self._clear(self.outline_list)

        self._counts['outline'] = len(outline)
        self._update_heading()

        if not outline:
            self.outline_list.append(_placeholder_row(
                "Sin estructura aún.\n\n"
                "Añade un acto con:\n# ACTO 1\n\n"
                "Añade una secuencia con:\n## SECUENCIA 1\n\n"
                "Añade una escena con:\nINT. LUGAR - DÍA"))
            return

        config = {
            'ACT':   {'emoji': EMOJI_ACT, 'indent': 8, 'bold': True},
            'SEQ':   {'emoji': EMOJI_SEQ, 'indent': 24, 'bold': True},
            'SCENE': {'emoji': EMOJI_SCENE, 'indent': 44, 'bold': False},
        }
        flags = outline_move_flags(outline)

        for index, item in enumerate(outline):
            cfg = config.get(item['type'], config['SCENE'])
            row = Gtk.ListBoxRow()
            row.scene_line = item['line']
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_top(3)
            box.set_margin_bottom(3)
            box.set_margin_start(cfg['indent'])
            box.set_margin_end(6)
            box.append(_emoji(cfg['emoji']))
            label = Gtk.Label(label=item['text'], xalign=0, hexpand=True)
            label.set_ellipsize(3)
            label.set_tooltip_text(item['text'])
            if cfg['bold']:
                label.add_css_class('heading')
            box.append(label)

            # Los controles mueven el bloque estructural completo.
            controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            can_up, can_down = flags[index]
            for direction, icon_name, tooltip, enabled in (
                (-1, 'go-up-symbolic', 'Mover arriba', can_up),
                (1, 'go-down-symbolic', 'Mover abajo', can_down),
            ):
                button = Gtk.Button.new_from_icon_name(icon_name)
                button.add_css_class('flat')
                button.add_css_class('circular')
                button.set_tooltip_text(tooltip if enabled else 'No se puede mover más en esa dirección')
                button.set_sensitive(enabled)
                button.set_valign(Gtk.Align.CENTER)
                button.connect('clicked', self._on_move_clicked, index, direction)
                controls.append(button)
            box.append(controls)
            row.set_child(box)
            self.outline_list.append(row)
            self._outline_rows.append(row)
        self._restore_scroll(self._outline_scroll, scroll_value)

    def _on_move_clicked(self, _button, index, direction):
        if self.on_move_outline_item:
            self.on_move_outline_item(index, direction)

    def _on_outline_activated(self, _lb, row):
        if row is None or not hasattr(row, 'scene_line'):
            return
        if self.on_scene_activate:
            self.on_scene_activate(row.scene_line)

    # ───────────────────────── Escaleta ─────────────────────────

    @staticmethod
    def _synopsis(text, outline, scene):
        line_end = text.find('\n', scene['offset'])
        start = len(text) if line_end < 0 else line_end + 1
        following = next((item['offset'] for item in outline
                          if item['offset'] > scene['offset']), len(text))
        body = text[start:following]
        synopsis = next((line.strip() for line in body.splitlines() if line.strip()),
                        'Sin acción descrita todavía.')
        if len(synopsis) > 115:
            synopsis = synopsis[:112].rstrip() + '…'
        return synopsis

    def set_escaleta(self, text, outline):
        scenes = [item for item in outline if item['type'] == 'SCENE']
        data = [(scene, self._synopsis(text, outline, scene)) for scene in scenes]
        signature = [(scene['text'], synopsis) for scene, synopsis in data]
        if signature == self._escaleta_sig:
            for row, (scene, _s) in zip(self._escaleta_rows, data):
                row.scene_line = scene['line']
            return
        self._escaleta_sig = signature
        self._escaleta_rows = []
        scroll_value = self._scroll_value(self._escaleta_scroll)
        self._clear(self.escaleta_list)

        self._counts['escaleta'] = len(scenes)
        self._update_heading()

        if not scenes:
            self.escaleta_list.append(_placeholder_row(
                "La escaleta aparecerá aquí al añadir encabezados de escena."))
            return

        for number, (scene, synopsis) in enumerate(data, 1):
            row = Gtk.ListBoxRow()
            row.scene_line = scene['line']
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            card.set_margin_top(7)
            card.set_margin_bottom(7)
            card.set_margin_start(12)
            card.set_margin_end(12)
            heading = Gtk.Label(label=f"{EMOJI_SCENE} ESCENA {number:02d}", xalign=0)
            heading.add_css_class('caption')
            heading.add_css_class('dim-label')
            title = Gtk.Label(label=scene['text'], xalign=0, wrap=True)
            title.add_css_class('heading')
            summary = Gtk.Label(label=synopsis, xalign=0, wrap=True)
            summary.add_css_class('dim-label')
            card.append(heading)
            card.append(title)
            card.append(summary)
            row.set_child(card)
            self.escaleta_list.append(row)
            self._escaleta_rows.append(row)
        self._restore_scroll(self._escaleta_scroll, scroll_value)

    def _on_escaleta_activated(self, _lb, row):
        if row is not None and hasattr(row, 'scene_line') and self.on_scene_activate:
            self.on_scene_activate(row.scene_line)

    # ───────────────────────── Personajes / Locaciones ─────────────────────────

    def _fill_names(self, listbox, names, attr, glyph, empty_text, bold):
        self._clear(listbox)
        if not names:
            listbox.append(_placeholder_row(empty_text))
            return
        for name in names:
            row = Gtk.ListBoxRow()
            setattr(row, attr, name)
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_top(5)
            box.set_margin_bottom(5)
            box.set_margin_start(12)
            box.set_margin_end(12)
            box.append(_emoji(glyph))
            label = Gtk.Label(label=name, xalign=0, hexpand=True)
            label.set_ellipsize(3)
            if bold:
                label.add_css_class('heading')
            box.append(label)
            row.set_child(box)
            row.set_tooltip_text('Clic para ir a la siguiente aparición')
            listbox.append(row)

    def set_characters(self, characters):
        self._counts['characters'] = len(characters)
        self._update_heading()
        self._fill_names(self.chars_list, characters, 'character_name', EMOJI_CHARACTER,
                         "Aún no hay personajes.\n\nEscribe un nombre en mayúsculas "
                         "sobre su diálogo y aparecerá aquí.", True)

    def _on_character_activated(self, _lb, row):
        if row is None or not hasattr(row, 'character_name'):
            return
        if self.on_character_activate:
            self.on_character_activate(row.character_name)

    def set_locations(self, locations):
        self._counts['locations'] = len(locations)
        self._update_heading()
        self._fill_names(self.locs_list, locations, 'location_name', EMOJI_LOCATION,
                         "Aún no hay locaciones.\n\nCrea una escena con "
                         "INT. o EXT. y aparecerá aquí.", False)

    def _on_location_activated(self, _lb, row):
        if row is None or not hasattr(row, 'location_name'):
            return
        if self.on_location_activate:
            self.on_location_activate(row.location_name)
