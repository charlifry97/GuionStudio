# window.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import json
from pathlib import Path

from gi.repository import Gtk, Adw, Gio, GLib, Pango

from .script_page import ScriptPage
from .exporter import export_html, export_txt, export_fountain, export_rtf
from .project_io import load_recent, add_recent, remove_recent, safe_file_stem
from .docx_export import write_docx, write_script_docx
from .pdf_export import write_script_pdf
from .icons import home_icon_bytes


WELCOME = (
    "# ACTO 1: PLANTEAMIENTO\n\n"
    "## SECUENCIA 1: EL MUNDO ORDINARIO\n\n"
    "EXT. CASA DE LA FAMILIA - AMANECER\n\n"
    "El sol asoma sobre un bosque frondoso. Una casa humilde duerme al borde del camino.\n\n"
    "INT. COCINA - DÍA\n\n"
    "CAPERUCITA, diez años, ayuda a su MADRE a preparar una cesta de pan y miel.\n\n"
    "MADRE\n"
    "(con cariño)\n"
    "Lleva esto a casa de la abuela. Y no te apartes del camino.\n\n"
    "CAPERUCITA\n"
    "Lo prometo, mamá.\n\n"
    "## SECUENCIA 2: EL INCIDENTE INCITADOR\n\n"
    "EXT. SENDERO DEL BOSQUE - DÍA\n\n"
    "Caperucita camina con su capa roja entre los árboles. Un LOBO emerge de los arbustos.\n\n"
    "LOBO\n"
    "(dulce)\n"
    "¿A dónde vas tan sola, pequeña?\n\n"
    "CAPERUCITA\n"
    "A casa de mi abuela, al otro lado del bosque.\n\n"
    "> CORTE A:\n\n"
    "# ACTO 2: CONFRONTACIÓN\n\n"
    "## SECUENCIA 3: ASCENSO\n\n"
    "EXT. BOSQUE - TARDE\n\n"
    "El lobo se adelanta entre las sombras. Conoce un atajo.\n\n"
    "## SECUENCIA 4: PUNTO MEDIO\n\n"
    "INT. CASA DE LA ABUELA - TARDE\n\n"
    "El lobo llega primero. Encierra a la abuela en el armario y se mete en su cama.\n\n"
    "## SECUENCIA 5: COMPLICACIÓN\n\n"
    "EXT. CLARO DEL BOSQUE - ATARDECER\n\n"
    "Caperucita se entretiene recogiendo flores. No ve el sol caer.\n\n"
    "## SECUENCIA 6: NOCHE OSCURA\n\n"
    "INT. CASA DE LA ABUELA - NOCHE\n\n"
    "Caperucita entra. La abuela tiene los ojos muy abiertos, muy grandes.\n\n"
    "CAPERUCITA\n"
    "Abuela, ¡qué ojos tan grandes tienes!\n\n"
    "LOBO\n"
    "Para verte mejor, querida.\n\n"
    "> CORTE A:\n\n"
    "# ACTO 3: RESOLUCIÓN\n\n"
    "## SECUENCIA 7: CLÍMAX\n\n"
    "INT. CASA DE LA ABUELA - NOCHE\n\n"
    "El lobo se abalanza. Un LEÑADOR irrumpe por la puerta y lo ahuyenta con su hacha.\n\n"
    "LEÑADOR\n"
    "¡Fuera de aquí, bestia!\n\n"
    "## SECUENCIA 8: NUEVO MUNDO\n\n"
    "EXT. CASA DE LA ABUELA - AMANECER\n\n"
    "La abuela y Caperucita salen al sol. La cesta sigue intacta sobre la mesa.\n\n"
    "CAPERUCITA\n"
    "La próxima vez, no me apartaré del camino.\n\n"
    "> FUNDIDO A NEGRO:\n"
)

# (etiqueta, acción, atajo predeterminado)
SHORTCUT_ACTIONS = (
    ('Nueva pestaña', 'win.new', '<Control>n'),
    ('Abrir', 'win.open', '<Control>o'),
    ('Guardar', 'win.save', '<Control>s'),
    ('Guardar como', 'win.save-as', '<Control><Shift>s'),
    ('Exportar', 'win.export', '<Control>e'),
    ('Exportar historia a Word', 'win.export-story', '<Control><Shift>e'),
    ('Editar título del proyecto', 'win.edit-title', 'F2'),
    ('Cerrar pestaña', 'win.close-tab', '<Control>w'),
    ('Ir al inicio', 'win.home', '<Alt>Home'),
    ('Ir al guion', 'win.view-script', '<Control><Shift>g'),
    ('Ir a la historia', 'win.view-story', '<Control><Shift>h'),
    ('Acción', 'win.format-action', '<Control>1'),
    ('Escena', 'win.format-scene', '<Control>2'),
    ('Personaje', 'win.format-character', '<Control>3'),
    ('Diálogo', 'win.format-dialogue', '<Control>4'),
    ('Acotación', 'win.format-parenthetical', '<Control>5'),
    ('Transición', 'win.format-transition', '<Control>6'),
    ('Acto', 'win.format-act', '<Control>7'),
    ('Secuencia', 'win.format-seq', '<Control>8'),
    ('Resaltar selección', 'win.highlight-apply', '<Control><Alt>h'),
    ('Borrar resaltado', 'win.highlight-clear', '<Control><Alt>b'),
    ('Mostrar categoría 1', 'win.highlight-filter-1', '<Control><Alt>1'),
    ('Mostrar categoría 2', 'win.highlight-filter-2', '<Control><Alt>2'),
    ('Mostrar categoría 3', 'win.highlight-filter-3', '<Control><Alt>3'),
    ('Mostrar categoría 4', 'win.highlight-filter-4', '<Control><Alt>4'),
    ('Mostrar todo', 'win.highlight-show-all', '<Control><Alt>0'),
)

# Acciones que requieren un documento abierto…
DOC_ACTIONS = ('save', 'save-as', 'export', 'export-story', 'edit-title',
               'story-sections', 'view-script', 'view-story')
# …y las que además solo tienen sentido en el espacio del guion.
SCRIPT_ONLY_ACTIONS = (
    'format-action', 'format-scene', 'format-character', 'format-dialogue',
    'format-parenthetical', 'format-transition', 'format-act', 'format-seq',
    'highlight-apply', 'highlight-clear',
    'highlight-filter-1', 'highlight-filter-2',
    'highlight-filter-3', 'highlight-filter-4', 'highlight-show-all',
)


def is_valid_accelerator(accel):
    """True si `accel` (formato GTK, p. ej. <Control>s) es válido o está vacío."""
    if not accel:
        return True
    try:
        result = Gtk.accelerator_parse(accel)
    except Exception:
        return False
    ok = result[0] if isinstance(result, tuple) else bool(result)
    return bool(ok)


def _is_dismissed(error):
    """¿El usuario cerró el selector de archivos sin elegir nada?"""
    try:
        return (error.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED)
                or error.matches(Gtk.dialog_error_quark(), Gtk.DialogError.CANCELLED)
                or error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED))
    except Exception:
        return 'dismiss' in (getattr(error, 'message', '') or '').lower()


def _error_text(error):
    return getattr(error, 'strerror', None) or str(error)


class GuionstudioWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'GuionstudioWindow'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(1200, 800)
        self.set_title("GuionStudio")

        self.home_tab = None
        self._last_page = None
        self._syncing = False
        self._syncing_title = False
        self._allow_close = False

        self._install_styles()
        self._build_actions()
        self._build_ui()
        self._create_home_tab()
        self.tab_view.set_selected_page(self.home_tab)
        self._sync_chrome()
        self.connect('close-request', self._on_close_request)

    # ───────────────────────── estilos ─────────────────────────

    def _install_styles(self):
        """Estilo visual coherente y superficies discretamente translúcidas.

        Solo se usan colores con nombre que libadwaita define de verdad
        (@window_bg_color, @card_bg_color, @accent_bg_color). Los antiguos
        @borders y @dim_color no existen y hacían que se descartaran reglas.
        """
        css = b"""
        .guionstudio-toolbar { padding: 5px 10px; }
        .guionstudio-toolbar button { border-radius: 10px; }
        .suggestion-popover,
        .suggestion-popover > contents {
            background-color: alpha(@window_bg_color, 0.5);
            border-radius: 12px;
        }
        .suggestion-popover listview,
        .suggestion-popover row { background-color: alpha(@window_bg_color, 0.5); }
        .suggestion-popover row { padding: 2px; }
        .section-heading { font-weight: 700; }
        .emoji-glyph { font-size: 15px; min-width: 22px; }
        .sidebar-tab { font-size: 16px; padding: 4px 6px; }
        .view-switch button { font-weight: 600; }
        .header-btn { font-size: 16px; min-width: 34px; }
        entry.title-entry { min-width: 260px; font-weight: 700; background: alpha(currentColor, 0.07); border-radius: 10px; }

        .home-page { background: @window_bg_color; }
        .home-hero { background: linear-gradient(135deg, #172b4d, #49365f); border-radius: 22px; padding: 30px; color: #fff; }
        .home-hero-title { color: #fff; font-size: 30px; font-weight: 800; }
        .home-hero-subtitle { color: alpha(#ffffff, 0.82); font-size: 14px; }
        .home-kicker { color: #e7bd78; font-weight: 800; letter-spacing: 2px; }
        .home-section-title { font-size: 19px; font-weight: 700; }
        .home-emoji { font-size: 28px; }
        button.home-card { background: alpha(@card_bg_color, 0.72); border: 1px solid alpha(currentColor, 0.15); border-radius: 16px; padding: 16px; box-shadow: none; }
        button.home-card:hover { background: alpha(@accent_bg_color, 0.14); }
        .home-card-title { font-weight: 700; font-size: 15px; }
        button.home-primary { background: #b77d3e; color: #fff; font-weight: 700; border-radius: 12px; padding: 9px 18px; box-shadow: none; }
        button.home-primary:hover { background: #c58a4a; }
        button.home-primary:active { background: #a06c33; }
        button.home-secondary { background: alpha(#ffffff, 0.16); color: #fff; font-weight: 600; border-radius: 12px; padding: 9px 18px; box-shadow: none; }
        button.home-secondary:hover { background: alpha(#ffffff, 0.26); }
        .home-recent-row { padding: 9px 12px; border-radius: 10px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        display = self.get_display()
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self._css_provider = provider

    # ───────────────────────── acciones ─────────────────────────

    def _build_actions(self):
        for name, cb in [
            ('new', self.new_tab),
            ('home', self.show_home),
            ('open', self.open_file),
            ('save', self.save_current),
            ('save-as', self.save_as_current),
            ('export', self.export_dialog),
            ('export-story', self.export_story_word),
            ('edit-title', self.edit_title),
            ('story-sections', self.show_story),
            ('view-story', self.show_story),
            ('view-script', self.show_script),
            ('shortcuts', self.shortcuts_dialog),
            ('highlight-apply', self.apply_highlight),
            ('highlight-clear', self.clear_highlight),
            ('highlight-filter-1', lambda: self.filter_highlight(0)),
            ('highlight-filter-2', lambda: self.filter_highlight(1)),
            ('highlight-filter-3', lambda: self.filter_highlight(2)),
            ('highlight-filter-4', lambda: self.filter_highlight(3)),
            ('highlight-show-all', self.show_all_highlights),
            ('close-tab', self.close_current_tab),
        ]:
            act = Gio.SimpleAction.new(name, None)
            act.connect('activate', lambda *_, cb=cb: cb())
            self.add_action(act)

        self._format_map = {
            'action': 'ACTION',
            'scene': 'SCENE',
            'character': 'CHARACTER',
            'dialogue': 'DIALOGUE',
            'parenthetical': 'PARENTHETICAL',
            'transition': 'TRANSITION',
            'act': 'ACT',
            'seq': 'SEQ',
        }
        for key, elem in self._format_map.items():
            act = Gio.SimpleAction.new(f'format-{key}', None)
            act.connect('activate', lambda *_, e=elem: self._set_element(e))
            self.add_action(act)

    def _script_page(self):
        """La página actual solo si está en el espacio del guion."""
        page = self.current_page()
        return page if page and page.view_name == 'script' else None

    def _set_element(self, element):
        page = self._script_page()
        if page:
            page.editor.set_element_type(element)
            page.editor.view.grab_focus()

    def apply_highlight(self):
        page = self._script_page()
        if page:
            page.editor.apply_highlight()
              
    def clear_highlight(self):
        page = self._script_page()
        if page:
            page.editor.clear_highlight_selection()

    def filter_highlight(self, index):
        page = self._script_page()
        if not page:
            return
        names = list(page.editor.highlight_categories)
        if index >= len(names):
            page.toast(f'No hay una categoría {index + 1}')
            return
        page.editor.set_highlight_filter(names[index])
        if page.editor.highlight_filter:
            page.toast(f"Mostrando: {names[index]}")

    def show_all_highlights(self):
        page = self._script_page()
        if page:
            page.editor.set_highlight_filter(None)
            page.toast('Texto completo visible')

    # ───────────────────────── interfaz ─────────────────────────

    def _build_ui(self):
        header = Adw.HeaderBar()

        # Etiquetas con emoji en lugar de iconos del tema: «sidebar-show-symbolic»
        # y otros no existen en todos los sistemas y el botón salía en blanco.
        self.sidebar_btn = Gtk.ToggleButton(label='📑')
        self.sidebar_btn.add_css_class('header-btn')
        self.sidebar_btn.set_active(True)
        self.sidebar_btn.set_tooltip_text("Mostrar/ocultar el panel lateral")
        self.sidebar_btn.connect('toggled', self._on_sidebar_toggled)
        header.pack_start(self.sidebar_btn)

        self.home_btn = Gtk.Button(label='🏠')
        self.home_btn.add_css_class('header-btn')
        self.home_btn.set_tooltip_text('Ir al inicio (Alt+Inicio)')
        self.home_btn.connect('clicked', lambda *_: self.show_home())
        header.pack_start(self.home_btn)

        # Selector de espacio de trabajo: Guion | Historia
        self.view_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.view_box.add_css_class('linked')
        self.view_box.add_css_class('view-switch')
        self.view_script_btn = Gtk.ToggleButton(label='🎬 Guion')
        self.view_script_btn.set_tooltip_text('Espacio de trabajo del guion (Ctrl+Mayús+G)')
        self.view_story_btn = Gtk.ToggleButton(label='📝 Historia')
        self.view_story_btn.set_tooltip_text(
            'Argumento, sinopsis, storyline y logline (Ctrl+Mayús+H)')
        self.view_story_btn.set_group(self.view_script_btn)
        self.view_script_btn.set_active(True)
        self.view_script_btn.connect('toggled', self._on_view_toggled, 'script')
        self.view_story_btn.connect('toggled', self._on_view_toggled, 'story')
        self.view_box.append(self.view_script_btn)
        self.view_box.append(self.view_story_btn)
        header.pack_start(self.view_box)

        # Título del proyecto: campo editable en el centro de la cabecera.
        self.title_stack = Gtk.Stack()
        app_title = Gtk.Label(label='GuionStudio')
        app_title.add_css_class('heading')
        self.title_stack.add_named(app_title, 'home')
        self.title_entry = Gtk.Entry()
        self.title_entry.add_css_class('title-entry')
        self.title_entry.set_placeholder_text('✏️ Título del proyecto')
        self.title_entry.set_tooltip_text('Título del proyecto (F2). Se guarda con el archivo y se usa al exportar.')
        self.title_entry.set_max_length(120)
        self.title_entry.set_property('xalign', 0.5)
        self.title_entry.connect('changed', self._on_title_changed)
        self.title_entry.connect('activate', self._on_title_activated)
        self.title_stack.add_named(self.title_entry, 'doc')
        self.title_stack.set_visible_child_name('home')
        header.set_title_widget(self.title_stack)

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text("Menú principal")
        menu_button.set_menu_model(self._build_menu())
        header.pack_end(menu_button)

        self.save_btn = Gtk.Button(label='💾')
        self.save_btn.add_css_class('header-btn')
        self.save_btn.set_tooltip_text("Guardar (Ctrl+S)")
        self.save_btn.connect('clicked', lambda *_: self.save_current())
        header.pack_end(self.save_btn)

        new_btn = Gtk.Button(label='➕')
        new_btn.add_css_class('header-btn')
        new_btn.set_tooltip_text("Nuevo guion (Ctrl+N)")
        new_btn.connect('clicked', lambda *_: self.new_tab())
        header.pack_end(new_btn)

        self.tab_view = Adw.TabView()
        self.tab_view.set_vexpand(True)
        self.tab_view.set_hexpand(True)
        self.tab_view.connect('notify::selected-page', self._on_tab_changed)
        self.tab_view.connect('close-page', self._on_close_page)

        self.tab_bar = Adw.TabBar()
        self.tab_bar.set_view(self.tab_view)
        self.tab_bar.set_autohide(False)

        # AdwToolbarView reparte el espacio correctamente: el contenido
        # (pestañas) ocupa todo lo que queda bajo las barras.
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.add_top_bar(self.tab_bar)
        toolbar_view.set_content(self.tab_view)
        self.set_content(toolbar_view)

    def _build_menu(self):
        menu = Gio.Menu()

        file_section = Gio.Menu()
        file_section.append("🏠 Inicio", "win.home")
        file_section.append("Nuevo guion", "win.new")
        file_section.append("Abrir…", "win.open")
        file_section.append("✏️ Título del proyecto", "win.edit-title")
        file_section.append("Cerrar pestaña", "win.close-tab")
        menu.append_section(None, file_section)

        save_section = Gio.Menu()
        save_section.append("Guardar", "win.save")
        save_section.append("Guardar como…", "win.save-as")
        menu.append_section(None, save_section)

        export_section = Gio.Menu()
        export_section.append("Exportar guion…", "win.export")
        export_section.append("📄 Exportar historia a Word…", "win.export-story")
        menu.append_section(None, export_section)

        view_section = Gio.Menu()
        view_section.append("🎬 Espacio del guion", "win.view-script")
        view_section.append("📝 Espacio de la historia", "win.view-story")
        menu.append_section(None, view_section)

        fmt = Gio.Menu()
        fmt.append("Acción", "win.format-action")
        fmt.append("Encabezado de escena", "win.format-scene")
        fmt.append("Personaje", "win.format-character")
        fmt.append("Diálogo", "win.format-dialogue")
        fmt.append("Acotación", "win.format-parenthetical")
        fmt.append("Transición", "win.format-transition")
        fmt.append("Acto", "win.format-act")
        fmt.append("Secuencia", "win.format-seq")
        menu.append_submenu("Formato", fmt)

        highlight = Gio.Menu()
        highlight.append('Resaltar selección (Ctrl+Alt+H)', 'win.highlight-apply')
        highlight.append('Ver categoría 1 (Ctrl+Alt+1)', 'win.highlight-filter-1')
        highlight.append('Ver categoría 2 (Ctrl+Alt+2)', 'win.highlight-filter-2')
        highlight.append('Ver categoría 3 (Ctrl+Alt+3)', 'win.highlight-filter-3')
        highlight.append('Ver categoría 4 (Ctrl+Alt+4)', 'win.highlight-filter-4')
        highlight.append('Mostrar todo (Ctrl+Alt+0)', 'win.highlight-show-all')
        menu.append_submenu('Resaltado', highlight)

        tools = Gio.Menu()
        tools.append('Atajos de teclado…', 'win.shortcuts')
        menu.append_section(None, tools)

        app_section = Gio.Menu()
        app_section.append("Acerca de", "app.about")
        app_section.append("Salir", "app.quit")
        menu.append_section(None, app_section)

        return menu

    # ───────────────────────── estado de la interfaz ─────────────────────────

    def _sync_chrome(self, *args):
        """Alinea botones, acciones y título con la pestaña actual.

        En Inicio, las acciones de documento se desactivan en lugar de no
        hacer nada en silencio.
        """
        page = self.current_page()
        has_doc = page is not None
        in_script = has_doc and page.view_name == 'script'

        for name in DOC_ACTIONS:
            action = self.lookup_action(name)
            if action:
                action.set_enabled(has_doc)
        for name in SCRIPT_ONLY_ACTIONS:
            action = self.lookup_action(name)
            if action:
                action.set_enabled(in_script)

        self.sidebar_btn.set_sensitive(has_doc)
        self.save_btn.set_sensitive(has_doc)
        self.view_box.set_visible(has_doc)

        if has_doc:
            self._syncing = True
            try:
                if page.view_name == 'story':
                    self.view_story_btn.set_active(True)
                else:
                    self.view_script_btn.set_active(True)
            finally:
                self._syncing = False
            page.set_sidebar_visible(self.sidebar_btn.get_active())
            self._syncing_title = True
            try:
                if self.title_entry.get_text() != page.project_title:
                    self.title_entry.set_text(page.project_title)
            finally:
                self._syncing_title = False
        self.title_stack.set_visible_child_name('doc' if has_doc else 'home')
        self._update_window_title()

    # ───────────────────────── título del proyecto ─────────────────────────

    def _on_title_changed(self, entry):
        if self._syncing_title:
            return
        page = self.current_page()
        if page:
            page.set_project_title(entry.get_text())

    def _on_title_activated(self, _entry):
        page = self.current_page()
        if page:
            page.focus_active_view()

    def edit_title(self):
        page = self.current_page()
        if page:
            self.title_entry.grab_focus()
            self.title_entry.select_region(0, -1)

    def _on_view_toggled(self, button, name):
        if self._syncing or not button.get_active():
            return
        page = self.current_page()
        if page:
            page.show_view(name)

    def current_page(self):
        tab = self.tab_view.get_selected_page()
        if tab:
            child = tab.get_child()
            # Durante append(), GTK puede emitir selected-page antes de que
            # se haya creado la portada. Solo una ScriptPage es un documento
            # editable; la portada y otros widgets no lo son.
            return child if isinstance(child, ScriptPage) else None
        return None

    def _script_pages(self):
        pages = []
        for index in range(self.tab_view.get_n_pages()):
            child = self.tab_view.get_nth_page(index).get_child()
            if isinstance(child, ScriptPage):
                pages.append(child)
        return pages

    def _tool_target_page(self):
        """Documento sobre el que actúan las herramientas lanzadas desde Inicio:
        el abierto actualmente o, si estás en Inicio, el último que usaste."""
        page = self.current_page()
        if page:
            return page
        pages = self._script_pages()
        if self._last_page in pages:
            return self._last_page
        return pages[-1] if pages else None

    def _select_page(self, page):
        if page.tab_page:
            self.tab_view.set_selected_page(page.tab_page)

    def toast(self, message):
        page = self.current_page()
        if page:
            page.toast(message)
        else:
            self.home_toasts.add_toast(Adw.Toast.new(message))

    # ───────────────────────── historia / guion ─────────────────────────

    def show_story(self):
        """Abre el espacio de trabajo de la historia del documento activo."""
        page = self._tool_target_page() or self.new_tab()
        self._select_page(page)
        page.show_view('story')

    def show_script(self):
        page = self._tool_target_page()
        if page:
            self._select_page(page)
            page.show_view('script')

    # ───────────────────────── atajos de teclado ─────────────────────────

    def shortcuts_dialog(self):
        app = self.get_application()
        config_dir = Path(GLib.get_user_config_dir()) / 'guionstudio'
        config_file = config_dir / 'shortcuts.json'
        try:
            saved = json.loads(config_file.read_text(encoding='utf-8')) if config_file.exists() else {}
            if not isinstance(saved, dict):
                saved = {}
        except (OSError, ValueError):
            saved = {}
        dialog = Gtk.Dialog(title='Atajos de teclado', transient_for=self, modal=True)
        dialog.add_button('Restaurar predeterminados', Gtk.ResponseType.APPLY)
        dialog.add_button('Cancelar', Gtk.ResponseType.CANCEL)
        dialog.add_button('Guardar atajos', Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(520, 620)
        outer = dialog.get_content_area()
        outer.set_spacing(8)
        outer.set_margin_top(12); outer.set_margin_bottom(12)
        outer.set_margin_start(12); outer.set_margin_end(12)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(box)
        scroll.set_vexpand(True)
        scroll.set_min_content_height(380)
        outer.append(scroll)

        entries = {}
        for label, action, default in SHORTCUT_ACTIONS:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            text = Gtk.Label(label=label, xalign=0, hexpand=True)
            entry = Gtk.Entry(text=saved.get(action, default)); entry.set_width_chars(24)
            entry.set_tooltip_text('Formato GTK: <Control>s, <Control><Shift>s, <Alt>1, etc.')
            row.append(text); row.append(entry); box.append(row)
            entries[action] = (entry, default)
        note = Gtk.Label(label='Escribe los modificadores y la tecla en formato GTK. '
                               'Deja vacío para quitar un atajo.', wrap=True, xalign=0)
        note.add_css_class('dim-label'); outer.append(note)
        problem = Gtk.Label(label='', wrap=True, xalign=0)
        problem.add_css_class('error'); outer.append(problem)

        def finish(_dialog, response):
            if response == Gtk.ResponseType.APPLY:
                for entry, default in entries.values():
                    entry.set_text(default)
                    entry.remove_css_class('error')
                problem.set_text('')
                return
            if response == Gtk.ResponseType.ACCEPT:
                values = {action: entry.get_text().strip()
                          for action, (entry, _default) in entries.items()}
                invalid = [a for a, v in values.items() if not is_valid_accelerator(v)]
                seen = {}
                duplicated = set()
                for action, value in values.items():
                    if value:
                        if value in seen:
                            duplicated.update((action, seen[value]))
                        seen[value] = action
                for action, (entry, _d) in entries.items():
                    if action in invalid or action in duplicated:
                        entry.add_css_class('error')
                    else:
                        entry.remove_css_class('error')
                if invalid or duplicated:
                    problem.set_text('Hay atajos no válidos o repetidos (marcados en rojo). '
                                     'Corrígelos para guardar.')
                    return  # el diálogo sigue abierto
                try:
                    config_dir.mkdir(parents=True, exist_ok=True)
                    config_file.write_text(json.dumps(values, ensure_ascii=False, indent=2),
                                           encoding='utf-8')
                except OSError as error:
                    problem.set_text(f'No se pudieron guardar los atajos: {_error_text(error)}')
                    return
                for action, accel in values.items():
                    app.set_accels_for_action(action, [accel] if accel else [])
                self.toast('Atajos de teclado guardados')
            dialog.destroy()
        dialog.connect('response', finish); dialog.present()

    # ───────────────────────── Inicio ─────────────────────────

    def _create_home_tab(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.add_css_class('home-page')
        clamp = Adw.Clamp()
        clamp.set_maximum_size(940)
        clamp.set_tightening_threshold(700)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        outer.set_margin_top(26); outer.set_margin_bottom(30)
        outer.set_margin_start(24); outer.set_margin_end(24)
        clamp.set_child(outer)
        scroll.set_child(clamp)
        self.home_page = scroll

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        hero.add_css_class('home-hero')
        kicker = Gtk.Label(label='EL ARTE DE CONTAR HISTORIAS', xalign=0)
        kicker.add_css_class('home-kicker')
        title = Gtk.Label(label='GuionStudio', xalign=0)
        title.add_css_class('home-hero-title')
        subtitle = Gtk.Label(label='Un espacio para imaginar, estructurar y escribir historias para la pantalla.',
                             xalign=0, wrap=True)
        subtitle.add_css_class('home-hero-subtitle')
        hero.append(kicker); hero.append(title); hero.append(subtitle)
        hero_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hero_actions.set_margin_top(6)
        create = Gtk.Button(label='✍️  Crear nuevo guion')
        create.add_css_class('home-primary')
        create.connect('clicked', lambda *_: self.new_tab())
        open_btn = Gtk.Button(label='📂  Abrir proyecto')
        open_btn.add_css_class('home-secondary')
        open_btn.connect('clicked', lambda *_: self.open_file())
        hero_actions.append(create); hero_actions.append(open_btn); hero.append(hero_actions)
        outer.append(hero)

        section = Gtk.Label(label='Tu mesa de trabajo', xalign=0)
        section.add_css_class('home-section-title'); outer.append(section)
        cards = Gtk.Grid(); cards.set_column_spacing(12); cards.set_row_spacing(12)
        cards.set_column_homogeneous(True)
        card_specs = [
            ('✍️', 'Nuevo guion', 'Empieza una historia desde una página en blanco.', self.new_tab),
            ('📂', 'Abrir proyecto', 'Continúa trabajando en un archivo existente.', self.open_file),
            ('📝', 'Desarrollo de la historia',
             'Argumento, sinopsis, storyline y logline en su propio espacio de trabajo.',
             self._open_story_from_home),
            ('⌨️', 'Atajos y herramientas', 'Consulta y personaliza los comandos del editor.',
             self.shortcuts_dialog),
        ]
        for index, (emoji, heading, detail, callback) in enumerate(card_specs):
            cards.attach(self._make_home_card(emoji, heading, detail, callback),
                         index % 2, index // 2, 1, 1)
        outer.append(cards)

        recent_title = Gtk.Label(label='Proyectos recientes', xalign=0)
        recent_title.add_css_class('home-section-title'); outer.append(recent_title)
        self.recent_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.append(self.recent_box)
        self._refresh_recent_projects()

        tips = Gtk.Label(
            label='Ctrl+N nuevo guion · Ctrl+O abrir · Ctrl+S guardar · '
                  'Alt+Inicio volver aquí · Ctrl+Mayús+H abrir la historia',
            xalign=0, wrap=True)
        tips.add_css_class('dim-label'); tips.add_css_class('caption')
        outer.append(tips)

        # La portada tiene su propio ToastOverlay: antes los avisos lanzados
        # desde Inicio (errores al abrir, etc.) no tenían dónde mostrarse.
        self.home_toasts = Adw.ToastOverlay()
        self.home_toasts.set_child(scroll)

        self.home_tab = self.tab_view.append(self.home_toasts)
        self.home_tab.set_title('Inicio')
        icon = self._home_tab_icon()
        if icon is not None:
            self.home_tab.set_icon(icon)
        self.home_tab.set_tooltip('Pantalla de inicio de GuionStudio')
        # Fija a la izquierda y sin botón de cerrar.
        self.tab_view.set_page_pinned(self.home_tab, True)

    @staticmethod
    def _home_tab_icon():
        """Icono propio (imagen incrustada): una pestaña fijada solo muestra
        icono, y los del tema no existen en todos los sistemas."""
        try:
            return Gio.BytesIcon.new(GLib.Bytes.new(home_icon_bytes()))
        except Exception:
            return None

    def _make_home_card(self, emoji, heading, detail, callback):
        button = Gtk.Button()
        button.add_css_class('home-card')
        button.set_hexpand(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        glyph = Gtk.Label(label=emoji, xalign=0)
        glyph.add_css_class('home-emoji')
        label = Gtk.Label(label=heading, xalign=0, hexpand=True)
        label.add_css_class('home-card-title')
        desc = Gtk.Label(label=detail, xalign=0, hexpand=True, wrap=True)
        desc.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        # Sin límite de ancho, el texto pedía su ancho natural completo y
        # ensanchaba las columnas más allá del contenedor.
        desc.set_max_width_chars(32)
        desc.add_css_class('dim-label')
        box.append(glyph); box.append(label); box.append(desc)
        button.set_child(box)
        button.connect('clicked', lambda _b, cb=callback: cb())
        return button

    def _open_story_from_home(self):
        self.show_story()

    def show_home(self, *args):
        if self.home_tab is not None:
            self._refresh_recent_projects()
            self.tab_view.set_selected_page(self.home_tab)

    # ───────────────────────── recientes ─────────────────────────

    def _recent_file_path(self):
        return str(Path(GLib.get_user_config_dir()) / 'guionstudio' / 'recent.json')

    def _remember_recent(self, path):
        add_recent(self._recent_file_path(), path)
        self._refresh_recent_projects()

    def _forget_recent(self, path):
        remove_recent(self._recent_file_path(), path)
        self._refresh_recent_projects()

    def _refresh_recent_projects(self):
        if not hasattr(self, 'recent_box'):
            return
        while child := self.recent_box.get_first_child():
            self.recent_box.remove(child)
        entries = load_recent(self._recent_file_path())
        if not entries:
            empty = Gtk.Label(label='Todavía no hay proyectos recientes. Crea un guion o abre uno para comenzar.',
                              xalign=0, wrap=True)
            empty.add_css_class('dim-label'); empty.set_margin_top(4)
            self.recent_box.append(empty)
            return
        for path in entries:
            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.add_css_class('home-recent-row')
            glyph = Gtk.Label(label='📄')
            glyph.add_css_class('emoji-glyph')
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2); info.set_hexpand(True)
            name = Gtk.Label(label=os.path.basename(path), xalign=0)
            name.set_ellipsize(Pango.EllipsizeMode.END)
            location = Gtk.Label(label=os.path.dirname(path), xalign=0)
            location.add_css_class('dim-label'); location.add_css_class('caption')
            location.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            info.append(name); info.append(location)
            row.append(glyph); row.append(info)
            open_recent = Gtk.Button(); open_recent.set_child(row); open_recent.add_css_class('flat')
            open_recent.set_hexpand(True)
            open_recent.set_tooltip_text(path)
            open_recent.connect('clicked', lambda _b, p=path: self.open_path(p))
            remove = Gtk.Button(label='✕')
            remove.add_css_class('flat'); remove.add_css_class('circular')
            remove.set_valign(Gtk.Align.CENTER)
            remove.set_tooltip_text('Quitar de la lista (no borra el archivo)')
            remove.connect('clicked', lambda _b, p=path: self._forget_recent(p))
            line.append(open_recent); line.append(remove)
            self.recent_box.append(line)

    # ───────────────────────── pestañas / documentos ─────────────────────────

    def _attach_page(self, page):
        tab = self.tab_view.append(page)
        page.tab_page = tab
        page.on_state_changed = self._update_window_title
        page.on_view_changed = self._sync_chrome
        page.on_export_story = self.export_story_word
        page._update_tab_state()
        self.tab_view.set_selected_page(tab)
        return tab

    def new_tab(self, *args, text=None):
        page = ScriptPage()
        page.set_text(WELCOME if text is None else text)
        self._attach_page(page)
        page.editor.view.grab_focus()
        return page

    def close_current_tab(self):
        tab = self.tab_view.get_selected_page()
        if tab and tab is not self.home_tab:
            self.tab_view.close_page(tab)

    def _on_close_page(self, tab_view, tab_page):
        """Impide cerrar la portada y pregunta antes de descartar cambios."""
        if tab_page is self.home_tab:
            tab_view.close_page_finish(tab_page, False)
            return True
        child = tab_page.get_child()
        if isinstance(child, ScriptPage) and child._modified:
            def decided(proceed):
                tab_view.close_page_finish(tab_page, proceed)
            self._ask_unsaved(child, decided)
            return True
        tab_view.close_page_finish(tab_page, True)
        return True

    def _ask_unsaved(self, page, decided):
        """Pregunta qué hacer con un documento modificado.

        Llama a decided(True) si se puede cerrar (guardado o descartado) y a
        decided(False) si se cancela o el guardado falla.
        """
        dialog = Adw.AlertDialog.new(
            f'¿Guardar los cambios de «{page.get_display_title()}»?',
            'Si no los guardas, se perderán los cambios hechos desde la última vez que guardaste.')
        dialog.add_response('cancel', 'Cancelar')
        dialog.add_response('discard', 'Descartar cambios')
        dialog.add_response('save', 'Guardar')
        dialog.set_response_appearance('discard', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance('save', Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response('save')
        dialog.set_close_response('cancel')

        def on_response(_dialog, response):
            if response == 'discard':
                decided(True)
            elif response == 'save':
                self._save_page(page, decided)
            else:
                decided(False)
        dialog.connect('response', on_response)
        self._select_page(page)
        dialog.present(self)

    def _on_close_request(self, *_args):
        if self._allow_close:
            return False
        dirty = [page for page in self._script_pages() if page._modified]
        if not dirty:
            return False
        names = '\n'.join(f'• {page.get_display_title()}' for page in dirty[:6])
        if len(dirty) > 6:
            names += f'\n… y {len(dirty) - 6} más'
        dialog = Adw.AlertDialog.new(
            '¿Salir con cambios sin guardar?',
            f'Estos documentos tienen cambios sin guardar:\n{names}')
        dialog.add_response('cancel', 'Cancelar')
        dialog.add_response('discard', 'Salir sin guardar')
        dialog.add_response('save', 'Guardar todo')
        dialog.set_response_appearance('discard', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance('save', Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response('save')
        dialog.set_close_response('cancel')

        def leave():
            self._allow_close = True
            self.close()

        def on_response(_dialog, response):
            if response == 'discard':
                leave()
            elif response == 'save':
                self._save_sequence(dirty, lambda ok: leave() if ok else None)
        dialog.connect('response', on_response)
        dialog.present(self)
        return True

    def _save_sequence(self, pages, done):
        if not pages:
            done(True)
            return
        page, rest = pages[0], pages[1:]
        self._select_page(page)
        self._save_page(page, lambda ok: self._save_sequence(rest, done) if ok else done(False))

    def _on_tab_changed(self, *args):
        page = self.current_page()
        if page:
            self._last_page = page
        self._sync_chrome()

    def _update_window_title(self, *args):
        page = self.current_page()
        if page:
            star = " •" if page._modified else ""
            self.set_title(f"{page.get_display_title()}{star} — GuionStudio")
        else:
            self.set_title("GuionStudio")

    def _on_sidebar_toggled(self, btn):
        page = self.current_page()
        if page:
            page.set_sidebar_visible(btn.get_active())

    # ───────────────────────── abrir ─────────────────────────

    def open_file(self):
        dlg = Gtk.FileDialog()
        dlg.set_title("Abrir guion")
        f_all = Gtk.FileFilter(); f_all.set_name("Todos los compatibles")
        for pattern in ("*.guion", "*.json", "*.fountain", "*.txt"):
            f_all.add_pattern(pattern)
        f1 = Gtk.FileFilter(); f1.set_name("Proyectos (*.guion, *.json)")
        f1.add_pattern("*.guion"); f1.add_pattern("*.json")
        f2 = Gtk.FileFilter(); f2.set_name("Fountain (*.fountain)"); f2.add_pattern("*.fountain")
        f3 = Gtk.FileFilter(); f3.set_name("Texto (*.txt)"); f3.add_pattern("*.txt")
        store = Gio.ListStore.new(Gtk.FileFilter)
        for f in (f_all, f1, f2, f3):
            store.append(f)
        dlg.set_filters(store)
        dlg.set_default_filter(f_all)
        dlg.open(self, None, self._on_open_done)

    def _on_open_done(self, dlg, result):
        try:
            f = dlg.open_finish(result)
        except GLib.Error as e:
            if not _is_dismissed(e):
                self.toast(f"No se pudo abrir: {e.message}")
            return
        if not f:
            return
        path = f.get_path()
        if not path:
            self.toast("Solo se pueden abrir archivos locales.")
            return
        self.open_path(path)

    def _find_open_page(self, path):
        target = os.path.realpath(path)
        for page in self._script_pages():
            for candidate in (page.current_file, page.imported_from):
                if candidate and os.path.realpath(candidate) == target:
                    return page
        return None

    def open_path(self, path):
        """Abre un archivo en una pestaña (o enfoca la que ya lo tiene abierto)."""
        existing = self._find_open_page(path)
        if existing:
            self._select_page(existing)
            existing.focus_active_view()
            existing.toast('Ese proyecto ya estaba abierto')
            return existing

        # La pestaña se crea solo si la lectura funciona; antes, un error dejaba
        # una pestaña «Sin título» vacía abandonada.
        page = ScriptPage()
        try:
            notice = page.load_from(path)
        except (OSError, ValueError) as error:
            self.toast(f"No se pudo abrir «{os.path.basename(path)}»: {_error_text(error)}")
            if not os.path.isfile(path):
                self._forget_recent(path)
            return None
        self._attach_page(page)
        self._remember_recent(path)
        page.toast(notice or f"Abierto: {os.path.basename(path)}")
        page.focus_active_view()
        return page

    # ───────────────────────── guardar ─────────────────────────

    def save_current(self):
        page = self.current_page()
        if page:
            self._save_page(page)

    def save_as_current(self):
        page = self.current_page()
        if page:
            self._save_as(page)

    def _save_page(self, page, done=None):
        if page.current_file:
            ok = self._do_save(page, page.current_file)
            if done:
                done(ok)
        else:
            self._save_as(page, done)

    def _save_as(self, page, done=None):
        dlg = Gtk.FileDialog()
        dlg.set_title("Guardar guion")
        dlg.set_initial_name(page.suggested_file_name())
        f = Gtk.FileFilter(); f.set_name("Proyecto de guion (*.guion)"); f.add_pattern("*.guion")
        store = Gio.ListStore.new(Gtk.FileFilter); store.append(f)
        dlg.set_filters(store)
        dlg.set_default_filter(f)
        dlg.save(self, None, lambda d, r: self._on_save_done(d, r, page, done))

    def _on_save_done(self, dlg, result, page, done=None):
        try:
            f = dlg.save_finish(result)
        except GLib.Error as e:
            if not _is_dismissed(e):
                page.toast(f"No se pudo guardar: {e.message}")
            if done:
                done(False)
            return
        path = f.get_path() if f else None
        if not path:
            if done:
                done(False)
            return
        if not path.lower().endswith(('.guion', '.json')):
            path += '.guion'
        ok = self._do_save(page, path)
        if done:
            done(ok)

    def _do_save(self, page, path):
        try:
            page.save_to(path)
        except OSError as error:
            page.toast(f"No se pudo guardar: {_error_text(error)}")
            return False
        self._remember_recent(path)
        page.toast(f"Guardado: {os.path.basename(path)}")
        self._update_window_title()
        return True

    # ───────────────────────── exportar ─────────────────────────

    def export_story_word(self, page=None):
        """Guarda en Word (.docx) el contenido del espacio de la historia."""
        page = page if isinstance(page, ScriptPage) else self.current_page()
        if not page:
            return
        if not page.story_export_sections():
            page.toast('La historia está vacía: escribe en alguna ficha antes de exportar.')
            return
        dlg = Gtk.FileDialog()
        dlg.set_title("Guardar la historia en Word")
        stem = safe_file_stem(page.project_title) or \
            os.path.splitext(page.get_display_title())[0] or "Historia"
        dlg.set_initial_name(f"{stem} - Historia.docx")
        f = Gtk.FileFilter(); f.set_name("Documento de Word (*.docx)"); f.add_pattern("*.docx")
        store = Gio.ListStore.new(Gtk.FileFilter); store.append(f)
        dlg.set_filters(store)
        dlg.set_default_filter(f)
        dlg.save(self, None, lambda d, r: self._on_story_word_done(d, r, page))

    def _on_story_word_done(self, dlg, result, page):
        try:
            f = dlg.save_finish(result)
        except GLib.Error as e:
            if not _is_dismissed(e):
                page.toast(f"No se pudo exportar: {e.message}")
            return
        path = f.get_path() if f else None
        if not path:
            return
        if not path.lower().endswith('.docx'):
            path += '.docx'
        sections = page.story_export_sections()
        title = page.project_title or os.path.splitext(page.get_display_title())[0]
        try:
            write_docx(path, title, sections, subtitle='Desarrollo de la historia')
        except OSError as error:
            page.toast(f"No se pudo exportar: {_error_text(error)}")
            return
        page.toast(f"Historia guardada en Word: {os.path.basename(path)}")

    def export_dialog(self):
        page = self.current_page()
        if not page:
            return
        dlg = Gtk.FileDialog()
        dlg.set_title("Exportar guion")
        base = os.path.splitext(page.get_display_title())[0] or "guion"
        dlg.set_initial_name(base + ".docx")
        # Orden: primero los formatos solicitados (.docx, .pdf, .txt) y
        # después los que ya existían (HTML, RTF, Fountain) por compatibilidad.
        fd = Gtk.FileFilter(); fd.set_name("Documento de Word (*.docx)"); fd.add_pattern("*.docx")
        fp = Gtk.FileFilter(); fp.set_name("Documento PDF (*.pdf)"); fp.add_pattern("*.pdf")
        ft = Gtk.FileFilter(); ft.set_name("Texto plano (*.txt)"); ft.add_pattern("*.txt")
        fh = Gtk.FileFilter(); fh.set_name("HTML (*.html)"); fh.add_pattern("*.html")
        fw = Gtk.FileFilter(); fw.set_name("Word RTF (*.rtf)"); fw.add_pattern("*.rtf")
        ff = Gtk.FileFilter(); ff.set_name("Fountain (*.fountain)"); ff.add_pattern("*.fountain")
        store = Gio.ListStore.new(Gtk.FileFilter)
        for f in (fd, fp, ft, fh, fw, ff):
            store.append(f)
        dlg.set_filters(store)
        dlg.set_default_filter(fd)
        dlg.save(self, None, lambda d, r: self._on_export_done(d, r, page))

    def _on_export_done(self, dlg, result, page):
        try:
            f = dlg.save_finish(result)
        except GLib.Error as e:
            if not _is_dismissed(e):
                page.toast(f"No se pudo exportar: {e.message}")
            return
        path = f.get_path() if f else None
        if not path:
            return
        lowered = path.lower()
        if not lowered.endswith(('.docx', '.pdf', '.html', '.rtf', '.fountain', '.txt')):
            path += '.docx'
            lowered = path.lower()
        text = page.get_text()
        title = page.project_title or os.path.splitext(page.get_display_title())[0] or "Guion"

        try:
            if lowered.endswith('.docx'):
                write_script_docx(path, text, title)
            elif lowered.endswith('.pdf'):
                write_script_pdf(path, text, title)
            elif lowered.endswith('.html'):
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(export_html(text, title))
            elif lowered.endswith('.rtf'):
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(export_rtf(text))
            elif lowered.endswith('.fountain'):
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(export_fountain(text))
            else:
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(export_txt(text))
        except OSError as error:
            page.toast(f"No se pudo exportar: {_error_text(error)}")
            return
        page.toast(f"Exportado: {os.path.basename(path)}")
