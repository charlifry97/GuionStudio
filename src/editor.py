# editor.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Editor de guion con formateo en vivo, memoria y autocompletado."""
import re
import time
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, Pango
from .parser import (classify, extract_outline, word_count, page_estimate,
                     move_outline_spans, remap_ranges_after_swap,
                     normalize_structural_case, find_occurrence)
from .story_memory import StoryMemory


ELEMENT_CYCLE = ['ACT', 'SEQ', 'SCENE', 'ACTION',
                 'CHARACTER', 'PARENTHETICAL', 'DIALOGUE', 'TRANSITION']

ELEMENT_PREFIXES = {
    'SCENE': 'INT. ',
    'ACT': '# ',
    'SEQ': '## ',
}

DEFAULT_HIGHLIGHT_CATEGORIES = {
    'Investigación': '#FFF1A8', 'Revisar': '#FFC9C9',
    'Personaje': '#C9E7FF', 'Tema': '#D9F5D0',
}
HEX_COLOR_RE = re.compile(r'#[0-9A-Fa-f]{6}')

HIGHLIGHT_PALETTE = (
    ('Rojo',     ('#FFE0E0', '#FF8080', '#C62828')),
    ('Naranja',  ('#FFE9CC', '#FFA94D', '#D84315')),
    ('Amarillo', ('#FFF9C4', '#FFEB3B', '#F57F17')),
    ('Verde',    ('#E0F5E0', '#7CB342', '#2E7D32')),
    ('Cian',     ('#E0F7FA', '#4DD0E1', '#00796B')),
    ('Azul',     ('#E3F2FD', '#64B5F6', '#1565C0')),
    ('Morado',   ('#F3E5F5', '#BA68C8', '#6A1B9A')),
)
SHADE_LABELS = ('Claro', 'Medio', 'Oscuro')


class _ColorPaletteButton(Gtk.MenuButton):
    """Muestra un color y abre una paleta 7×3 al pulsarlo."""

    def __init__(self, color='#FFF1A8', on_selected=None):
        super().__init__()
        self._color = color
        self._on_selected = on_selected
        self._provider = None
        self._popover = Gtk.Popover()
        self._popover.set_child(self._build_grid())
        self.set_popover(self._popover)
        self.set_size_request(52, -1)
        self._refresh_swatch()

    @staticmethod
    def _apply_bg(widget, color):
        provider = Gtk.CssProvider()
        provider.load_from_data(
            (f'button{{background:{color};min-width:24px;min-height:24px;'
             f'padding:0;border-radius:6px;border:1px solid rgba(0,0,0,.25);}}').encode()
        )
        widget.get_style_context().add_provider(provider, 800)
        return provider

    def _build_grid(self):
        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        grid.set_margin_top(12); grid.set_margin_bottom(12)
        grid.set_margin_start(12); grid.set_margin_end(12)
        for r, (name, shades) in enumerate(HIGHLIGHT_PALETTE):
            lbl = Gtk.Label(label=name, xalign=0)
            lbl.add_css_class('dim-label')
            lbl.set_width_chars(9)
            grid.attach(lbl, 0, r, 1, 1)
            for c, (shade, shade_name) in enumerate(zip(shades, SHADE_LABELS), start=1):
                btn = Gtk.Button()
                btn.set_size_request(30, 30)
                btn.set_tooltip_text(f'{name} · {shade_name}')
                self._apply_bg(btn, shade)
                btn.connect('clicked', self._pick, shade)
                grid.attach(btn, c, r, 1, 1)
        return grid

    def _pick(self, _btn, shade):
        self._color = shade
        self._refresh_swatch()
        self._popover.popdown()
        if self._on_selected:
            self._on_selected(shade)

    def _refresh_swatch(self):
        if self._provider is not None:
            self.get_style_context().remove_provider(self._provider)
        self._provider = self._apply_bg(self, self._color)

    def get_color(self):
        return self._color


def _strip_structural_prefix(text: str) -> str:
    text = text.strip()
    if text.startswith('##'):
        return text.lstrip('#').strip()
    if text.startswith('#'):
        return text.lstrip('#').strip()
    m = re.match(r'^(INT\.|EXT\.|INT/EXT\.|I/E\.|EST\.)\s+', text, re.IGNORECASE)
    if m:
        return text[m.end():].strip()
    return text


class ScriptEditor(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._pending = 0
        self._updating = False
        self.on_outline_changed = None
        self.on_user_changed = None
        self.on_memory_changed = None
        self.on_notice = None

        self.memory = StoryMemory()
        self._ac_cooldown = 0.0
        self._ac_prefix = ''
        self._ac_navigated = False
        self._norm_suspended_until = 0.0
        self._nav_mark = None
        self._status_base = ''

        self.buffer = Gtk.TextBuffer()
        self.view = Gtk.TextView(buffer=self.buffer)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(96)
        self.view.set_right_margin(96)
        self.view.set_top_margin(48)
        self.view.set_bottom_margin(48)

        self._create_tags()
        self.highlight_categories = dict(DEFAULT_HIGHLIGHT_CATEGORIES)
        self.active_highlight = 'Investigación'
        self.highlight_filter = None
        self._create_highlight_controls()
        self._create_autocomplete_widgets()
        self._create_edit_controls()

        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect('key-pressed', self._on_key_pressed)
        self.view.add_controller(key_controller)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.view)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        self.append(self.edit_bar)
        self.append(scrolled)
        self.append(self.highlight_bar)

        self.status = Gtk.Label(label="0 palabras · 0.0 páginas · 0 párrafos · 0 líneas · 0 caracteres")
        self.status.add_css_class('dim-label')
        self.status.set_margin_top(6)
        self.status.set_margin_bottom(6)
        self.append(self.status)

        self.buffer.connect('changed', self._on_changed)

    def _notify(self, message):
        if self.on_notice:
            self.on_notice(message)

    # ───────────────────── DESHACER / REHACER ─────────────────────

    def _create_edit_controls(self):
        self.edit_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.edit_bar.add_css_class('toolbar')
        self.edit_bar.set_margin_start(12)
        self.edit_bar.set_margin_end(12)
        self.edit_bar.set_margin_top(4)
        self.edit_bar.set_margin_bottom(2)

        self.undo_btn = Gtk.Button(label='↶ Deshacer')
        self.undo_btn.set_tooltip_text('Deshacer (Ctrl+Z)')
        self.undo_btn.connect('clicked', lambda *_: self.undo())
        self.edit_bar.append(self.undo_btn)

        self.redo_btn = Gtk.Button(label='↷ Rehacer')
        self.redo_btn.set_tooltip_text('Rehacer (Ctrl+Y)')
        self.redo_btn.connect('clicked', lambda *_: self.redo())
        self.edit_bar.append(self.redo_btn)

        self.buffer.connect('notify::can-undo', lambda *_: self._update_undo_buttons())
        self.buffer.connect('notify::can-redo', lambda *_: self._update_undo_buttons())
        self._update_undo_buttons()

    def _update_undo_buttons(self):
        self.undo_btn.set_sensitive(self.buffer.props.can_undo)
        self.redo_btn.set_sensitive(self.buffer.props.can_redo)

    def undo(self):
        if self.buffer.props.can_undo:
            self._norm_suspended_until = time.monotonic() + 3.0
            self.buffer.undo()
            self._update_undo_buttons()

    def redo(self):
        if self.buffer.props.can_redo:
            self._norm_suspended_until = time.monotonic() + 3.0
            self.buffer.redo()
            self._update_undo_buttons()

    # ───────────────────────── RESALTADO ─────────────────────────

    def _create_highlight_controls(self):
        self.highlight_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.highlight_bar.add_css_class('toolbar')
        self.highlight_bar.set_margin_start(12)
        self.highlight_bar.set_margin_end(12)
        self.highlight_bar.set_margin_top(6)
        self.highlight_bar.set_margin_bottom(2)
        self.category_model = Gtk.StringList.new(list(self.highlight_categories))
        self.category_drop = Gtk.DropDown(model=self.category_model)
        self.category_drop.set_hexpand(False)
        self.category_drop.connect('notify::selected', self._on_highlight_category_selected)
        category_label = Gtk.Label(label='🎨 Categoría:')
        category_label.add_css_class('dim-label')
        self.highlight_bar.append(category_label)
        self.highlight_bar.append(self.category_drop)

        apply_btn = Gtk.Button(label='🖍️ Resaltar')
        apply_btn.set_tooltip_text('Aplicar el color de la categoría al texto seleccionado (Ctrl+Alt+H)')
        apply_btn.connect('clicked', lambda *_: self.apply_highlight())
        self.highlight_bar.append(apply_btn)

        erase_btn = Gtk.Button(label='🧽 Borrar resaltado')
        erase_btn.set_tooltip_text('Quita el resaltado del texto seleccionado (Ctrl+Alt+B)')
        erase_btn.connect('clicked', lambda *_: self.clear_highlight_selection())
        self.highlight_bar.append(erase_btn)

        self.filter_menu_btn = Gtk.MenuButton(label='👁️ Ver solo ▾')
        self.filter_menu_btn.set_tooltip_text(
            'Elige una categoría para ver solo su texto resaltado')
        self._filter_popover = self._build_filter_popover()
        self.filter_menu_btn.set_popover(self._filter_popover)
        self.highlight_bar.append(self.filter_menu_btn)

        clear_btn = Gtk.Button(label='↔️ Mostrar todo')
        clear_btn.set_tooltip_text('Vuelve a mostrar y permite editar todo el texto (Ctrl+Alt+0)')
        clear_btn.connect('clicked', lambda *_: self.set_highlight_filter(None))
        self.highlight_bar.append(clear_btn)

        manage_btn = Gtk.Button(label='⚙️')
        manage_btn.set_tooltip_text('Gestionar categorías y colores')
        manage_btn.connect('clicked', lambda *_: self.manage_highlight_categories())
        self.highlight_bar.append(manage_btn)

    def _on_highlight_category_selected(self, dropdown, _pspec):
        idx = dropdown.get_selected()
        names = list(self.highlight_categories)
        if 0 <= idx < len(names):
            self.active_highlight = names[idx]

    def _refresh_category_dropdown(self):
        names = list(self.highlight_categories)
        self.category_model = Gtk.StringList.new(names)
        self.category_drop.set_model(self.category_model)
        if self.active_highlight not in self.highlight_categories:
            self.active_highlight = names[0] if names else ''
        if names:
            self.category_drop.set_selected(names.index(self.active_highlight))
        self._refresh_filter_popover()

    @staticmethod
    def _tag_slug(name):
        return re.sub(r'[^a-z0-9_]+', '_', name.lower()).strip('_') or 'custom'

    def _highlight_tag_name(self, category):
        return 'highlight_' + self._tag_slug(category)

    def _ensure_highlight_tag(self, name, color):
        tag_name = self._highlight_tag_name(name)
        tag = self.buffer.get_tag_table().lookup(tag_name)
        if tag is None:
            tag = self.buffer.create_tag(tag_name)
        rgba = Gdk.RGBA()
        rgba.parse(color)
        rgba.alpha = 0.5
        tag.set_property('background-rgba', rgba)
        tag.set_property('background-set', True)
        return tag_name

    def apply_highlight(self):
        bounds = self.buffer.get_selection_bounds()
        if not bounds:
            self._notify('Selecciona primero el texto que quieres resaltar.')
            return False
        if not self.active_highlight or self.active_highlight not in self.highlight_categories:
            return False
        start, end = bounds
        tag_name = self._ensure_highlight_tag(self.active_highlight,
                                              self.highlight_categories[self.active_highlight])
        self.buffer.apply_tag_by_name(tag_name, start, end)
        if self.on_user_changed:
            self.on_user_changed()
        if self.highlight_filter:
            self.set_highlight_filter(self.highlight_filter)
        return True

    def _build_filter_popover(self):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6); box.set_margin_bottom(6)
        box.set_margin_start(6); box.set_margin_end(6)

        title = Gtk.Label(label='Ver solo:', xalign=0)
        title.add_css_class('heading')
        title.set_margin_start(8); title.set_margin_end(8)
        title.set_margin_bottom(4)
        box.append(title)

        if not self.highlight_categories:
            empty = Gtk.Label(label='Sin categorías', xalign=0)
            empty.add_css_class('dim-label')
            empty.set_margin_start(8); empty.set_margin_end(8)
            box.append(empty)
        else:
            for name, color in self.highlight_categories.items():
                btn = Gtk.Button()
                btn.set_has_frame(False)
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row.set_margin_top(2); row.set_margin_bottom(2)
                row.set_margin_start(6); row.set_margin_end(6)

                check = Gtk.Label(label='✓' if self.highlight_filter == name else ' ')
                check.set_width_chars(1)
                row.append(check)

                swatch = Gtk.Box()
                swatch.set_size_request(16, 16)
                swatch.set_valign(Gtk.Align.CENTER)
                provider = Gtk.CssProvider()
                provider.load_from_data(
                    (f'.hl-swatch {{ background:{color}; border-radius:3px; '
                     f'border:1px solid rgba(0,0,0,.3); }}').encode()
                )
                swatch.add_css_class('hl-swatch')
                swatch.get_style_context().add_provider(provider, 800)
                row.append(swatch)

                lbl = Gtk.Label(label=name, xalign=0)
                row.append(lbl)

                btn.set_child(row)
                btn.connect('clicked', self._on_filter_clicked, name)
                box.append(btn)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        all_btn = Gtk.Button()
        all_btn.set_has_frame(False)
        all_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        all_row.set_margin_top(2); all_row.set_margin_bottom(2)
        all_row.set_margin_start(6); all_row.set_margin_end(6)
        all_check = Gtk.Label(label='✓' if not self.highlight_filter else ' ')
        all_check.set_width_chars(1)
        all_row.append(all_check)
        all_row.append(Gtk.Label(label='↔️ Mostrar todo', xalign=0))
        all_btn.set_child(all_row)
        all_btn.connect('clicked', self._on_filter_clicked, None)
        box.append(all_btn)

        popover.set_child(box)
        return popover

    def _on_filter_clicked(self, _btn, category):
        self._filter_popover.popdown()
        self.set_highlight_filter(category)
        if not category:
            self._notify('Mostrando todo el texto')

    def _refresh_filter_popover(self):
        if not hasattr(self, 'filter_menu_btn'):
            return
        self._filter_popover = self._build_filter_popover()
        self.filter_menu_btn.set_popover(self._filter_popover)

    def clear_highlight_selection(self):
        bounds = self.buffer.get_selection_bounds()
        if not bounds:
            self._notify('Selecciona primero el texto del que quieres quitar el resaltado.')
            return False
        start, end = bounds
        start_offset = start.get_offset()
        end_offset = end.get_offset()
        had_any = False
        for name in list(self.highlight_categories):
            tag = self.buffer.get_tag_table().lookup(self._highlight_tag_name(name))
            if not tag:
                continue
            for a, b in self._tag_ranges(tag):
                if b > start_offset and a < end_offset:
                    had_any = True
                    break
            self.buffer.remove_tag(tag, start, end)
        if self.on_user_changed:
            self.on_user_changed()
        if self.highlight_filter:
            self.set_highlight_filter(self.highlight_filter)
        self._notify('Resaltado eliminado' if had_any
                     else 'El texto seleccionado no tenía resaltado')
        return True

    def _tag_ranges(self, tag):
        ranges = []
        it = self.buffer.get_start_iter()
        run_start = 0 if it.has_tag(tag) else None
        while it.forward_to_tag_toggle(tag):
            offset = it.get_offset()
            if it.starts_tag(tag):
                run_start = offset
            elif run_start is not None:
                if offset > run_start:
                    ranges.append((run_start, offset))
                run_start = None
        if run_start is not None:
            total = self.buffer.get_char_count()
            if total > run_start:
                ranges.append((run_start, total))
        return ranges

    def _set_reading_mode(self, active):
        self.view.set_editable(not active)
        self.view.set_cursor_visible(not active)

    def set_highlight_filter(self, category):
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        self.buffer.remove_tag_by_name('filter_hidden', start, end)
        if not category or category not in self.highlight_categories:
            self.highlight_filter = None
            self._set_reading_mode(False)
            self._refresh_status()
            self._refresh_filter_popover()
            return
        tag = self.buffer.get_tag_table().lookup(self._highlight_tag_name(category))
        ranges = self._tag_ranges(tag) if tag else []
        if not ranges:
            self.highlight_filter = None
            self._set_reading_mode(False)
            self._refresh_status()
            self._notify(f'No hay texto resaltado en «{category}».')
            self._refresh_filter_popover()
            return
        total = self.buffer.get_char_count()
        cursor = 0
        for a, b in sorted(ranges):
            if a > cursor:
                self.buffer.apply_tag_by_name('filter_hidden',
                                              self.buffer.get_iter_at_offset(cursor),
                                              self.buffer.get_iter_at_offset(a))
            cursor = max(cursor, b)
        if cursor < total:
            self.buffer.apply_tag_by_name('filter_hidden',
                                          self.buffer.get_iter_at_offset(cursor),
                                          self.buffer.get_end_iter())
        self.highlight_filter = category
        self._set_reading_mode(True)
        self._refresh_status()
        self._refresh_filter_popover()

    def _collect_ranges(self):
        result = []
        for name in self.highlight_categories:
            tag = self.buffer.get_tag_table().lookup(self._highlight_tag_name(name))
            if not tag:
                continue
            for a, b in self._tag_ranges(tag):
                result.append({'category': name, 'start': a, 'end': b})
        return result

    def export_highlights(self):
        return {'categories': dict(self.highlight_categories),
                'ranges': self._collect_ranges()}

    def import_highlights(self, data):
        if not isinstance(data, dict):
            return
        cats = data.get('categories', {})
        if isinstance(cats, dict):
            valid = {name: color for name, color in cats.items()
                     if isinstance(name, str) and name.strip()
                     and isinstance(color, str) and HEX_COLOR_RE.fullmatch(color)}
            if valid:
                self.highlight_categories = valid
        self._refresh_category_dropdown()
        total = self.buffer.get_char_count()
        for item in data.get('ranges', []):
            try:
                name = item['category']
                a = int(item['start'])
                b = int(item['end'])
                if name not in self.highlight_categories:
                    continue
                a = max(0, min(a, total))
                b = max(a, min(b, total))
                if b > a:
                    tag = self._ensure_highlight_tag(name, self.highlight_categories[name])
                    self.buffer.apply_tag_by_name(tag, self.buffer.get_iter_at_offset(a),
                                                  self.buffer.get_iter_at_offset(b))
            except (KeyError, TypeError, ValueError):
                continue

    def manage_highlight_categories(self):
        root = self.get_root()
        dialog = Gtk.Dialog(title='Categorías de resaltado', transient_for=root, modal=True)
        dialog.add_button('Cancelar', Gtk.ResponseType.CANCEL)
        dialog.add_button('Guardar categorías', Gtk.ResponseType.ACCEPT)
        box = dialog.get_content_area()
        box.set_spacing(8); box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)
        rows = []
        original_names = list(self.highlight_categories)
        for name, color in self.highlight_categories.items():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            n = Gtk.Entry(text=name); n.set_hexpand(True)
            c = _ColorPaletteButton(color=color)
            row.append(n); row.append(c); box.append(row); rows.append((n, c))
        add = Gtk.Button(label='➕ Añadir categoría')

        def add_row(*_):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            n = Gtk.Entry(placeholder_text='Nombre de categoría'); n.set_hexpand(True)
            c = _ColorPaletteButton(color='#E8D5FF')
            row.append(n); row.append(c)
            box.insert_child_after(row, add.get_prev_sibling())
            rows.append((n, c))
        add.connect('clicked', add_row); box.append(add)
        note = Gtk.Label(label='El color es un código hexadecimal de 6 cifras. '
                               'Una categoría sin nombre se elimina.', wrap=True, xalign=0)
        note.add_css_class('dim-label'); box.append(note)

        def done(_dlg, response):
            if response == Gtk.ResponseType.ACCEPT:
                updated = {}
                for n, c in rows:
                    name = n.get_text().strip()
                    color = c.get_color() if isinstance(c, _ColorPaletteButton) else c.get_text().strip()
                    if name and HEX_COLOR_RE.fullmatch(color):
                        updated[name] = color
                if updated:
                    previous = self._collect_ranges()
                    renames = {}
                    for index, old_name in enumerate(original_names):
                        new_name = rows[index][0].get_text().strip() if index < len(rows) else ''
                        if new_name and new_name in updated:
                            renames[old_name] = new_name
                    start, end = self.buffer.get_start_iter(), self.buffer.get_end_iter()
                    for old_name in original_names:
                        tag = self.buffer.get_tag_table().lookup(self._highlight_tag_name(old_name))
                        if tag:
                            self.buffer.remove_tag(tag, start, end)
                    self.set_highlight_filter(None)
                    self.highlight_categories = updated
                    self.active_highlight = next(iter(updated))
                    self._refresh_category_dropdown()
                    for name, color in updated.items():
                        self._ensure_highlight_tag(name, color)
                    total = self.buffer.get_char_count()
                    for item in previous:
                        new_name = renames.get(item['category'])
                        if not new_name:
                            continue
                        a = max(0, min(item['start'], total))
                        b = max(a, min(item['end'], total))
                        if b > a:
                            self.buffer.apply_tag_by_name(
                                self._highlight_tag_name(new_name),
                                self.buffer.get_iter_at_offset(a),
                                self.buffer.get_iter_at_offset(b))
                    if self.on_user_changed:
                        self.on_user_changed()
                else:
                    self._notify('Se necesita al menos una categoría con nombre y color válido.')
            dialog.destroy()
        dialog.connect('response', done); dialog.present()

    # ───────────────────────── TAGS ─────────────────────────

    def _create_tags(self):
        b = self.buffer
        hidden = b.create_tag('filter_hidden')
        hidden.set_property('invisible', True)
        mono = "Monospace"

        t = b.create_tag('act')
        t.set_property('weight', Pango.Weight.BOLD)
        t.set_property('scale', 1.6)
        t.set_property('foreground', '#1c71d8')
        t.set_property('justification', Gtk.Justification.CENTER)
        t.set_property('pixels-above-lines', 24)
        t.set_property('pixels-below-lines', 16)

        t = b.create_tag('seq')
        t.set_property('weight', Pango.Weight.BOLD)
        t.set_property('scale', 1.3)
        t.set_property('justification', Gtk.Justification.CENTER)
        t.set_property('pixels-above-lines', 18)
        t.set_property('pixels-below-lines', 12)

        t = b.create_tag('scene')
        t.set_property('weight', Pango.Weight.BOLD)
        t.set_property('family', mono)
        t.set_property('foreground', '#1a5fb4')
        t.set_property('pixels-above-lines', 16)
        t.set_property('pixels-below-lines', 8)

        t = b.create_tag('action')
        t.set_property('family', mono)

        t = b.create_tag('character')
        t.set_property('weight', Pango.Weight.BOLD)
        t.set_property('family', mono)
        t.set_property('left-margin', 180)
        t.set_property('pixels-above-lines', 10)

        t = b.create_tag('parenthetical')
        t.set_property('family', mono)
        t.set_property('style', Pango.Style.ITALIC)
        t.set_property('left-margin', 150)
        t.set_property('right-margin', 110)

        t = b.create_tag('dialogue')
        t.set_property('family', mono)
        t.set_property('left-margin', 110)
        t.set_property('right-margin', 110)

        t = b.create_tag('transition')
        t.set_property('family', mono)
        t.set_property('weight', Pango.Weight.BOLD)
        t.set_property('justification', Gtk.Justification.RIGHT)
        t.set_property('pixels-above-lines', 12)
        t.set_property('pixels-below-lines', 6)

    # ───────────────────── AUTOCOMPLETADO ─────────────────────

    def _create_autocomplete_widgets(self):
        self._ac_list = Gtk.ListBox()
        self._ac_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._ac_list.connect('row-activated', self._on_ac_row_activated)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self._ac_list)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(240)
        scroll.set_propagate_natural_height(True)

        self._ac_popover = Gtk.Popover()
        self._ac_popover.add_css_class('suggestion-popover')
        self._ac_popover.set_child(scroll)
        self._ac_popover.set_autohide(False)
        self._ac_popover.set_has_arrow(True)

    def _on_ac_row_activated(self, _lb, row):
        self._accept_autocomplete()

    def _maybe_show_autocomplete(self):
        if self._updating or not self.view.get_editable():
            return
        if time.monotonic() < self._ac_cooldown:
            return

        buffer = self.buffer
        insert = buffer.get_insert()
        it = buffer.get_iter_at_mark(insert)

        line_start = it.copy()
        line_start.set_line_offset(0)
        before = buffer.get_text(line_start, it, True)

        match = re.search(r'([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)$', before)
        if not match:
            self._hide_autocomplete()
            return

        prefix = match.group(1)
        if len(prefix) < 2:
            self._hide_autocomplete()
            return

        line_type = self._detect_current_type()
        suggestions = self.memory.suggestions(prefix, exclude_word=prefix)

        if line_type == 'CHARACTER':
            suggestions = [s for s in suggestions if s['kind'] == 'character']
        elif line_type == 'SCENE':
            suggestions = [s for s in suggestions if s['kind'] == 'location']
        elif line_type == 'ACTION':
            pass
        else:
            self._hide_autocomplete()
            return

        if not suggestions:
            self._hide_autocomplete()
            return

        self._show_autocomplete(suggestions, prefix, it)

    def _show_autocomplete(self, suggestions, prefix, it):
        while (child := self._ac_list.get_first_child()):
            self._ac_list.remove(child)

        for s in suggestions[:8]:
            row = Gtk.ListBoxRow()
            row._suggestion = s
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.append(Gtk.Label(label=s['icon']))
            box.append(Gtk.Label(label=s['name'], xalign=0, hexpand=True))
            kind_label = Gtk.Label(
                label=('personaje' if s['kind'] == 'character' else 'locación'),
                xalign=1,
            )
            kind_label.add_css_class('dim-label')
            box.append(kind_label)
            row.set_child(box)
            self._ac_list.append(row)

        loc = self.view.get_iter_location(it)
        x, y = self.view.buffer_to_window_coords(
            Gtk.TextWindowType.WIDGET, loc.x, loc.y + loc.height)
        rect = Gdk.Rectangle()
        rect.x, rect.y = x, y
        rect.width = 1
        rect.height = 1

        if self._ac_popover.get_parent() is None:
            self._ac_popover.set_parent(self.view)
        self._ac_popover.set_pointing_to(rect)

        if not self._ac_popover.get_visible():
            self._ac_popover.popup()

        first = self._ac_list.get_row_at_index(0)
        if first:
            self._ac_list.select_row(first)
        self._ac_prefix = prefix
        self._ac_navigated = False

    def _hide_autocomplete(self):
        if self._ac_popover.get_parent() is not None:
            self._ac_popover.popdown()

    def _accept_autocomplete(self):
        row = self._ac_list.get_selected_row()
        if not row or not hasattr(row, '_suggestion'):
            self._hide_autocomplete()
            return

        word = row._suggestion['name']
        buffer = self.buffer
        end = buffer.get_iter_at_mark(buffer.get_insert())
        start = end.copy()
        start.backward_chars(len(self._ac_prefix))

        buffer.begin_user_action()
        buffer.delete(start, end)
        buffer.insert(start, word)
        buffer.end_user_action()

        buffer.place_cursor(start)

        self._hide_autocomplete()
        self._ac_cooldown = time.monotonic() + 0.5

    def _move_ac_selection(self, delta):
        row = self._ac_list.get_selected_row()
        if not row:
            return
        self._ac_navigated = True
        new_row = self._ac_list.get_row_at_index(row.get_index() + delta)
        if new_row:
            self._ac_list.select_row(new_row)

    # ───────────────────── TECLADO ─────────────────────

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        if self._ac_popover.get_visible():
            if keyval == Gdk.KEY_Escape:
                self._hide_autocomplete()
                return True
            if keyval == Gdk.KEY_Tab:
                self._accept_autocomplete()
                return True
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                if self._ac_navigated:
                    self._accept_autocomplete()
                    return True
                self._hide_autocomplete()
                return False
            if keyval == Gdk.KEY_Down:
                self._move_ac_selection(1)
                return True
            if keyval == Gdk.KEY_Up:
                self._move_ac_selection(-1)
                return True
            if keyval in (Gdk.KEY_Left, Gdk.KEY_Right,
                          Gdk.KEY_Home, Gdk.KEY_End):
                self._hide_autocomplete()

        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and keyval in (Gdk.KEY_z, Gdk.KEY_Z, Gdk.KEY_y, Gdk.KEY_Y):
            self._norm_suspended_until = time.monotonic() + 3.0
            return False

        if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
                return False
            if not self.view.get_editable():
                return False
            shift = keyval == Gdk.KEY_ISO_Left_Tab or bool(state & Gdk.ModifierType.SHIFT_MASK)
            self.cycle_element_type(-1 if shift else 1)
            return True
        return False

    # ───────────────────── BUFFER / FORMATO ─────────────────────

    def _apply_formatting(self, text=None, classified=None):
        self._updating = True
        try:
            start_it = self.buffer.get_start_iter()
            end_it = self.buffer.get_end_iter()
            if text is None:
                text = self.buffer.get_text(start_it, end_it, True)
            if classified is None:
                classified = classify(text)

            for name in ('act', 'seq', 'scene', 'character', 'dialogue',
                         'parenthetical', 'transition', 'action'):
                self.buffer.remove_tag_by_name(name, start_it, end_it)

            for s, e, cls in classified:
                if cls == 'BLANK':
                    continue
                tag = cls.lower()
                si = self.buffer.get_iter_at_offset(s)
                ei = self.buffer.get_iter_at_offset(e)
                self.buffer.apply_tag_by_name(tag, si, ei)

            paragraphs = sum(1 for block in re.split(r"\n\s*\n", text.strip()) if block.strip()) if text.strip() else 0
            lines = len(text.splitlines()) if text else 0
            characters = len(text)
            self._status_base = (
                f"{word_count(text)} palabras · {page_estimate(text):.1f} páginas · "
                f"{paragraphs} párrafos · {lines} líneas · {characters} caracteres"
            )
            self._refresh_status()
        finally:
            self._updating = False

    def _refresh_status(self):
        suffix = ''
        if self.highlight_filter:
            suffix = f'  ·  👁️ Modo lectura: «{self.highlight_filter}»'
        self.status.set_text(self._status_base + suffix)

    def _on_changed(self, _buf):
        if self._updating:
            return
        if self._pending:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(150, self._post_change)
        if self.on_user_changed:
            self.on_user_changed()

    def _flush_pending(self):
        if self._pending:
            GLib.source_remove(self._pending)
            self._pending = 0
        self._post_change()

    def _apply_case_normalization(self, text, normalized):
        old_lines = text.split('\n')
        new_lines = normalized.split('\n')
        if len(old_lines) != len(new_lines):
            return text
        buf = self.buffer
        cursor = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        shift = 0
        offset = 0
        self._updating = True
        buf.begin_user_action()
        try:
            for old, new in zip(old_lines, new_lines):
                if old != new:
                    limit = min(len(old), len(new))
                    p = 0
                    while p < limit and old[p] == new[p]:
                        p += 1
                    s = 0
                    while s < limit - p and old[len(old) - 1 - s] == new[len(new) - 1 - s]:
                        s += 1
                    a = offset + shift + p
                    b = offset + shift + len(old) - s
                    replacement = new[p:len(new) - s]
                    start_it = buf.get_iter_at_offset(a)
                    end_it = buf.get_iter_at_offset(b)
                    buf.delete(start_it, end_it)
                    buf.insert(start_it, replacement)
                    delta = len(replacement) - (b - a)
                    if cursor >= b:
                        cursor += delta
                    elif cursor > a:
                        cursor = a + min(cursor - a, len(replacement))
                    shift += delta
                offset += len(old) + 1
        finally:
            buf.end_user_action()
            self._updating = False
        buf.place_cursor(buf.get_iter_at_offset(max(0, min(cursor, buf.get_char_count()))))
        return normalized

    def _post_change(self):
        self._pending = 0
        text = self.get_text()
        if time.monotonic() >= self._norm_suspended_until:
            normalized = normalize_structural_case(text)
            if normalized != text:
                text = self._apply_case_normalization(text, normalized)
        classified = classify(text)
        self._apply_formatting(text, classified)
        if self.highlight_filter:
            self.set_highlight_filter(self.highlight_filter)
        if self.on_outline_changed:
            self.on_outline_changed(extract_outline(text, classified), text)
        if self.memory.update_from_text(text, classified):
            if self.on_memory_changed:
                self.on_memory_changed(self.memory.characters, self.memory.locations)
        self._maybe_show_autocomplete()
        return False

    def get_text(self) -> str:
        return self.buffer.get_text(
            self.buffer.get_start_iter(),
            self.buffer.get_end_iter(), True,
        )

    def set_text(self, text: str):
        self._hide_autocomplete()
        if self._pending:
            GLib.source_remove(self._pending)
            self._pending = 0
        text = normalize_structural_case(text)
        self._updating = True
        try:
            self.buffer.begin_irreversible_action()
            self.buffer.set_text(text)
            self.buffer.end_irreversible_action()
        finally:
            self._updating = False
        self.set_highlight_filter(None)
        classified = classify(text)
        self._apply_formatting(text, classified)
        if self.on_outline_changed:
            self.on_outline_changed(extract_outline(text, classified), text)
        if self.memory.update_from_text(text, classified):
            if self.on_memory_changed:
                self.on_memory_changed(self.memory.characters, self.memory.locations)

    def move_outline_item(self, item_index: int, direction: int):
        if not self.view.get_editable():
            self._notify('Pulsa «Mostrar todo» antes de reorganizar la estructura.')
            return False
        text = self.get_text()
        outline = extract_outline(text)
        spans = move_outline_spans(text, outline, item_index, direction)
        if spans is None:
            return False
        a0, a1, b0, b1 = spans

        self._hide_autocomplete()
        saved = [(item['category'], item['start'], item['end'])
                 for item in self._collect_ranges()]
        new_region = text[b0:b1] + text[a0:a1]

        buf = self.buffer
        buf.begin_user_action()
        buf.delete(buf.get_iter_at_offset(a0), buf.get_iter_at_offset(b1))
        buf.insert(buf.get_iter_at_offset(a0), new_region)
        buf.end_user_action()

        for category, start, end in saved:
            if category not in self.highlight_categories:
                continue
            for a, b in remap_ranges_after_swap([(start, end)], spans):
                if b > a:
                    tag = self._highlight_tag_name(category)
                    buf.apply_tag_by_name(tag, buf.get_iter_at_offset(a),
                                          buf.get_iter_at_offset(b))

        moved_start = a0 if direction == -1 else a0 + (b1 - b0)
        it = buf.get_iter_at_offset(moved_start)
        buf.place_cursor(it)
        self._flush_pending()
        self._scroll_to_iter(buf.get_iter_at_offset(moved_start))
        return True

    # ───────────────────── NAVEGACIÓN ─────────────────────

    def _scroll_to_iter(self, it):
        if self._nav_mark is None:
            self._nav_mark = self.buffer.create_mark('nav-target', it, False)
        else:
            self.buffer.move_mark(self._nav_mark, it)
        self.view.scroll_to_mark(self._nav_mark, 0.12, True, 0.0, 0.3)

    def scroll_to_line(self, line_num: int):
        if line_num < 1 or line_num > self.buffer.get_line_count():
            return
        result = self.buffer.get_iter_at_line(line_num - 1)
        it = result[1] if isinstance(result, tuple) else result
        self.buffer.place_cursor(it)
        self._scroll_to_iter(it)
        self.view.grab_focus()

    def find_and_jump(self, text):
        full = self.get_text()
        selection = self.buffer.get_selection_bounds()
        if selection:
            start_from = selection[1].get_offset()
        else:
            start_from = self.buffer.get_iter_at_mark(self.buffer.get_insert()).get_offset()
        found = find_occurrence(full, text, start_from)
        if found is None:
            self._notify(f'«{text}» no aparece en el texto.')
            return
        pos, length = found
        start = self.buffer.get_iter_at_offset(pos)
        end = self.buffer.get_iter_at_offset(pos + length)
        self.buffer.select_range(start, end)
        self._scroll_to_iter(start)
        self.view.grab_focus()

    # ───────────────────── TIPO DE ELEMENTO ─────────────────────

    def _current_line_range(self):
        mark = self.buffer.get_insert()
        it = self.buffer.get_iter_at_mark(mark)
        start = it.copy()
        start.set_line_offset(0)
        end = it.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        return start, end

    def _current_line_text(self):
        start, end = self._current_line_range()
        return self.buffer.get_text(start, end, True)

    def set_element_type(self, element: str):
        if element not in ELEMENT_CYCLE or not self.view.get_editable():
            return

        start, end = self._current_line_range()
        current = self.buffer.get_text(start, end, True)
        body = _strip_structural_prefix(current)

        if element in ('ACT', 'SEQ', 'SCENE', 'CHARACTER', 'TRANSITION'):
            body = body.upper()

        prefix = ELEMENT_PREFIXES.get(element, '')
        new_line = prefix + body

        self._hide_autocomplete()
        self.buffer.begin_user_action()
        self.buffer.delete(start, end)
        self.buffer.insert(start, new_line)
        self.buffer.end_user_action()

        self.buffer.place_cursor(start)
        self._ac_cooldown = time.monotonic() + 0.4
        self._flush_pending()

    def _detect_current_type(self) -> str:
        text = self._current_line_text().strip()
        if not text:
            return 'ACTION'
        if text.startswith('##'):
            return 'SEQ'
        if text.startswith('#'):
            return 'ACT'
        if re.match(r'^(INT\.|EXT\.|INT/EXT\.|I/E\.|EST\.)\s', text, re.IGNORECASE):
            return 'SCENE'
        if text.startswith('(') and text.endswith(')'):
            return 'PARENTHETICAL'
        if text.endswith('TO:') or text.startswith('>'):
            return 'TRANSITION'
        if text.isupper() and text[0].isalpha() and len(text) < 50:
            return 'CHARACTER'
        return 'ACTION'

    def cycle_element_type(self, direction: int = 1):
        current = self._detect_current_type()
        try:
            idx = ELEMENT_CYCLE.index(current)
        except ValueError:
            idx = 0
        new_idx = (idx + direction) % len(ELEMENT_CYCLE)
        self.set_element_type(ELEMENT_CYCLE[new_idx])
