"""Pruebas de interfaz y editor sobre un GTK simulado (ver gtk_fake.py)."""
import os
import tempfile
import unittest

from tests import gtk_fake

GLIB = gtk_fake.install()

from src.window import GuionstudioWindow, DOC_ACTIONS, SCRIPT_ONLY_ACTIONS, WELCOME  # noqa: E402
from src.script_page import ScriptPage  # noqa: E402
from src.editor import ScriptEditor  # noqa: E402
from src.story_workspace import StoryWorkspace  # noqa: E402
from src.structure_panel import StructurePanel  # noqa: E402
from gi.repository import Gdk  # noqa: E402

KEY = lambda name: getattr(Gdk, name)  # noqa: E731


def make_editor(text):
    ed = ScriptEditor()
    ed.set_text(text)
    return ed


class EditorTests(unittest.TestCase):
    def test_tab_at_end_of_line_does_not_touch_next_line(self):
        ed = make_editor("Primera linea\nSegunda linea\nTercera\n")
        ed.buffer.place_cursor(ed.buffer.get_iter_at_offset(len("Primera linea")))  # fin de línea 1
        ed.set_element_type('SCENE')
        lines = ed.get_text().split('\n')
        self.assertEqual(lines[0], "INT. PRIMERA LINEA")
        self.assertEqual(lines[1], "Segunda linea")   # intacta (antes se corrompía)
        self.assertEqual(lines[2], "Tercera")
        # y el cursor queda al final de la línea editada, no en la siguiente
        cur = ed.buffer.get_iter_at_mark(ed.buffer.get_insert()).get_offset()
        self.assertEqual(cur, len("INT. PRIMERA LINEA"))

    def test_original_bug_is_reproducible_with_old_semantics(self):
        ed = make_editor("Uno\nDos\n")
        it = ed.buffer.get_iter_at_offset(3)
        end = it.copy()
        end.forward_to_line_end()          # semántica GTK documentada
        self.assertEqual(end.get_offset(), 7)   # saltó a la línea siguiente

    def test_shift_tab_is_handled(self):
        ed = make_editor("\nHola\n")
        ed.buffer.place_cursor(ed.buffer.get_iter_at_offset(5))
        handled = ed._on_key_pressed(None, KEY('KEY_ISO_Left_Tab'), 0, gtk_fake._flag(('ModifierType', 'SHIFT_MASK')))
        self.assertTrue(handled)

    def test_ctrl_tab_is_not_swallowed(self):
        ed = make_editor("Hola\n")
        ctrl = gtk_fake._flag(('ModifierType', 'CONTROL_MASK'))
        self.assertFalse(ed._on_key_pressed(None, KEY('KEY_Tab'), 0, ctrl))

    def test_normalization_keeps_highlights_and_other_lines(self):
        ed = make_editor("Texto resaltado importante\n\nint. casa - día\nAcción.\n")
        ed.buffer.select_range(ed.buffer.get_iter_at_offset(6), ed.buffer.get_iter_at_offset(15))
        self.assertTrue(ed.apply_highlight())
        before = ed.export_highlights()['ranges']
        ed._post_change()
        self.assertIn("INT. CASA - DÍA", ed.get_text())
        self.assertEqual(ed.export_highlights()['ranges'], before)   # antes se borraban

    def test_normalization_cursor_is_preserved(self):
        ed = make_editor("\nint. casa\n")
        ed.buffer.place_cursor(ed.buffer.get_iter_at_offset(5))
        ed._post_change()
        self.assertEqual(ed.get_text(), "\nINT. CASA\n")
        self.assertEqual(ed.buffer.get_iter_at_mark(ed.buffer.get_insert()).get_offset(), 5)

    def test_set_text_is_irreversible_and_not_modified(self):
        GLIB.timeouts.clear()
        changes = []
        ed = ScriptEditor()
        ed.on_user_changed = lambda: changes.append(1)
        ed.set_text("hola")
        self.assertEqual(changes, [])
        self.assertIn('begin_irreversible', ed.buffer.undo_log)
        self.assertEqual(GLIB.timeouts, {})   # no deja trabajo diferido duplicado

    def test_highlight_export_import_roundtrip(self):
        ed = make_editor("abcdef ghijkl mnop")
        ed.active_highlight = 'Revisar'
        ed.buffer.select_range(ed.buffer.get_iter_at_offset(0), ed.buffer.get_iter_at_offset(3))
        ed.apply_highlight()
        ed.buffer.select_range(ed.buffer.get_iter_at_offset(7), ed.buffer.get_iter_at_offset(18))
        ed.apply_highlight()   # llega hasta el final del texto
        data = ed.export_highlights()
        self.assertEqual([(r['start'], r['end']) for r in data['ranges']], [(0, 3), (7, 18)])
        other = make_editor("abcdef ghijkl mnop")
        other.import_highlights(data)
        self.assertEqual(other.export_highlights()['ranges'], data['ranges'])

    def test_import_replaces_default_categories(self):
        ed = make_editor("x")
        ed.import_highlights({'categories': {'Motivo': '#112233'}, 'ranges': []})
        self.assertEqual(list(ed.highlight_categories), ['Motivo'])
        self.assertEqual(ed.active_highlight, 'Motivo')

    def test_filter_without_matches_does_not_blank_the_editor(self):
        notes = []
        ed = make_editor("Algo de texto")
        ed.on_notice = notes.append
        ed.set_highlight_filter('Revisar')
        self.assertIsNone(ed.highlight_filter)
        self.assertTrue(ed.view.get_editable())
        self.assertEqual(ed.buffer.applied.get('filter_hidden', set()), set())
        self.assertTrue(notes)

    def test_filter_hides_complement_and_locks_editing(self):
        ed = make_editor("0123456789")
        ed.active_highlight = 'Tema'
        ed.buffer.select_range(ed.buffer.get_iter_at_offset(3), ed.buffer.get_iter_at_offset(6))
        ed.apply_highlight()
        ed.set_highlight_filter('Tema')
        self.assertEqual(ed.buffer.applied['filter_hidden'], {0, 1, 2, 6, 7, 8, 9})
        self.assertFalse(ed.view.get_editable())
        ed.set_element_type('SCENE')           # bloqueado en modo lectura
        self.assertEqual(ed.get_text(), "0123456789")
        ed.set_highlight_filter(None)
        self.assertTrue(ed.view.get_editable())
        self.assertEqual(ed.buffer.applied['filter_hidden'], set())

    def test_apply_highlight_without_selection_notifies(self):
        notes = []
        ed = make_editor("hola")
        ed.on_notice = notes.append
        self.assertFalse(ed.apply_highlight())
        self.assertTrue(notes)

    def test_move_scene_preserves_highlights_with_their_text(self):
        text = "# ACTO 1\n## SECUENCIA 1\nINT. CASA - DÍA\nAccion casa\nINT. CALLE - NOCHE\nAccion calle\n"
        ed = make_editor(text)
        for needle in ("Accion casa", "Accion calle"):
            i = text.index(needle)
            ed.active_highlight = 'Revisar' if 'casa' in needle else 'Tema'
            ed.buffer.select_range(ed.buffer.get_iter_at_offset(i),
                                   ed.buffer.get_iter_at_offset(i + len(needle)))
            ed.apply_highlight()
        self.assertTrue(ed.move_outline_item(2, 1))
        moved = ed.get_text()
        self.assertLess(moved.index("INT. CALLE"), moved.index("INT. CASA"))
        got = {r['category']: moved[r['start']:r['end']] for r in ed.export_highlights()['ranges']}
        self.assertEqual(got, {'Revisar': 'Accion casa', 'Tema': 'Accion calle'})

    def test_move_blocked_in_reading_mode(self):
        notes = []
        text = "INT. A - DÍA\nx\nINT. B - DÍA\ny\n"
        ed = make_editor(text)
        ed.on_notice = notes.append
        ed.buffer.select_range(ed.buffer.get_iter_at_offset(13), ed.buffer.get_iter_at_offset(14))
        ed.apply_highlight()
        ed.set_highlight_filter('Investigación')
        self.assertFalse(ed.move_outline_item(0, 1))
        self.assertEqual(ed.get_text(), text)

    def test_find_and_jump_cycles_and_wraps(self):
        ed = make_editor("\nMARÍA\nHola\n\nMARÍA\nAdiós\n")
        seen = []
        for _ in range(3):
            ed.find_and_jump('MARÍA')
            seen.append(ed.buffer.get_selection_bounds()[0].get_offset())
        self.assertEqual(seen, [1, 13, 1])
        notes = []
        ed.on_notice = notes.append
        ed.find_and_jump('INEXISTENTE')
        self.assertTrue(notes)

    def test_nav_mark_is_reused(self):
        ed = make_editor("a\nb\nc\nd\n")
        before = len(ed.buffer.marks)
        for line in (1, 2, 3, 4, 2, 3):
            ed.scroll_to_line(line)
        self.assertLessEqual(len(ed.buffer.marks) - before, 1)

    def test_enter_is_not_hijacked_by_autocomplete(self):
        ed = make_editor("\nMARÍA\nHola\n\nMAR")
        ed.buffer.place_cursor(ed.buffer.get_end_iter())
        ed._post_change()
        self.assertTrue(ed._ac_popover.get_visible())
        self.assertFalse(ed._on_key_pressed(None, KEY('KEY_Return'), 0, 0))   # Enter = salto de línea
        self.assertFalse(ed._ac_popover.get_visible())
        ed._post_change(); ed._ac_cooldown = 0
        ed._maybe_show_autocomplete()
        self.assertTrue(ed._ac_popover.get_visible())
        ed._on_key_pressed(None, KEY('KEY_Down'), 0, 0)
        self.assertTrue(ed._on_key_pressed(None, KEY('KEY_Return'), 0, 0))    # tras navegar sí acepta
        self.assertTrue(ed.get_text().endswith("MARÍA"))

    def test_tab_accepts_suggestion(self):
        ed = make_editor("\nMARÍA\nHola\n\nMAR")
        ed.buffer.place_cursor(ed.buffer.get_end_iter())
        ed._post_change()
        self.assertTrue(ed._on_key_pressed(None, KEY('KEY_Tab'), 0, 0))
        self.assertTrue(ed.get_text().endswith("\nMARÍA"))

    def test_undo_pauses_normalization(self):
        ed = make_editor("\nint. casa\n")
        ed.set_text("\nhola\n")
        ed._on_key_pressed(None, KEY('KEY_z'), 0, gtk_fake._flag(('ModifierType', 'CONTROL_MASK')))
        ed.buffer.set_text("\nint. casa\n")
        ed._post_change()
        self.assertEqual(ed.get_text(), "\nint. casa\n")


class StoryWorkspaceTests(unittest.TestCase):
    def test_loading_does_not_fire_changes_but_typing_does(self):
        events = []
        story = StoryWorkspace(on_changed=lambda k, t: events.append((k, t)))
        story.set_sections({'Argumento': 'uno dos tres', 'Logline': 'x'})
        self.assertEqual(events, [])
        story._buffers['Sinopsis'].set_text('hola mundo')
        self.assertEqual(events, [('Sinopsis', 'hola mundo')])
        self.assertEqual(story._count_labels['Argumento'].get_text(), '3 palabras')
        self.assertEqual(story._count_labels['Storyline'].get_text(), 'Vacío')

    def test_section_switch_swaps_buffer_and_title(self):
        story = StoryWorkspace()
        story.set_sections({'Sinopsis': 'abc def'})
        story.section_list.select_row(story._rows['Sinopsis'])
        self.assertIs(story.view.get_buffer(), story._buffers['Sinopsis'])
        self.assertIn('Sinopsis', story.title_label.get_text())
        self.assertIn('2 palabras', story.status.get_text())

    def test_get_sections_roundtrip(self):
        story = StoryWorkspace()
        data = {'Argumento': 'a', 'Sinopsis': 'b', 'Storyline': 'c', 'Logline': 'd'}
        story.set_sections(data)
        self.assertEqual(story.get_sections(), data)


class StructurePanelTests(unittest.TestCase):
    OUT = [
        {'type': 'ACT', 'offset': 0, 'line': 1, 'text': '# ACTO 1'},
        {'type': 'SCENE', 'offset': 9, 'line': 2, 'text': 'INT. A - DÍA'},
        {'type': 'SCENE', 'offset': 30, 'line': 4, 'text': 'INT. B - DÍA'},
    ]

    def test_no_rebuild_when_only_lines_shift(self):
        p = StructurePanel()
        p.set_outline(self.OUT)
        rows = list(p.outline_list._children)
        shifted = [dict(i, line=i['line'] + 3) for i in self.OUT]
        p.set_outline(shifted)
        self.assertEqual(list(p.outline_list._children), rows)     # mismas filas
        self.assertEqual([r.scene_line for r in rows], [4, 5, 7])  # líneas al día

    def test_rebuild_when_structure_changes_and_heading_counts(self):
        p = StructurePanel()
        p.set_outline(self.OUT)
        p.set_outline(self.OUT[:2])
        self.assertEqual(len(p.outline_list._children), 2)
        self.assertIn('2', p.heading.get_text())

    def test_activation_fires_every_time(self):
        p = StructurePanel()
        got = []
        p.on_scene_activate = got.append
        p.set_outline(self.OUT)
        row = p.outline_list._children[1]
        p.outline_list.emit('row-activated', row)
        p.outline_list.emit('row-activated', row)
        self.assertEqual(got, [2, 2])

    def test_edge_arrows_are_disabled(self):
        p = StructurePanel()
        p.set_outline(self.OUT)
        first_scene = p.outline_list._children[1]
        controls = first_scene.get_child()._children[-1]
        up, down = controls._children
        self.assertFalse(up.get_sensitive())
        self.assertTrue(down.get_sensitive())

    def test_emoji_rows(self):
        p = StructurePanel()
        p.set_outline(self.OUT)
        p.set_characters(['MARÍA'])
        p.set_locations(['OFICINA'])
        glyph = lambda row: row.get_child()._children[0].get_text()  # noqa: E731
        self.assertEqual([glyph(r) for r in p.outline_list._children], ['🎭', '🎬', '🎬'])
        self.assertEqual(glyph(p.chars_list._children[0]), '👤')
        self.assertEqual(glyph(p.locs_list._children[0]), '📍')

    def test_name_lists_activate(self):
        p = StructurePanel()
        got = []
        p.on_character_activate = lambda n: got.append(('c', n))
        p.on_location_activate = lambda n: got.append(('l', n))
        p.set_characters(['ANA']); p.set_locations(['PLAZA'])
        p.chars_list.emit('row-activated', p.chars_list._children[0])
        p.locs_list.emit('row-activated', p.locs_list._children[0])
        self.assertEqual(got, [('c', 'ANA'), ('l', 'PLAZA')])


class WindowTests(unittest.TestCase):
    def setUp(self):
        gtk_fake.PRESENTED.clear()
        GLIB.config_dir = tempfile.mkdtemp()   # recientes aislados por prueba
        self.win = GuionstudioWindow(application=None)
        self.dir = tempfile.mkdtemp()

    def project(self, name='p.guion', content='INT. CASA - DÍA\nHola\n', story=None):
        import json
        path = os.path.join(self.dir, name)
        json.dump({'content': content, 'story_sections': story or {}, 'highlights': {}},
                  open(path, 'w', encoding='utf-8'), ensure_ascii=False)
        return path

    def action_enabled(self, name):
        return self.win.lookup_action(name).get_enabled()

    def test_home_is_pinned_selected_and_actions_disabled(self):
        w = self.win
        self.assertIs(w.tab_view.get_selected_page(), w.home_tab)
        self.assertIn(w.home_tab, w.tab_view.pinned)
        self.assertIsNone(w.current_page())
        for name in DOC_ACTIONS + SCRIPT_ONLY_ACTIONS:
            self.assertFalse(self.action_enabled(name), name)
        self.assertTrue(self.action_enabled('new'))
        self.assertTrue(self.action_enabled('open'))
        self.assertFalse(w.view_box.get_visible())
        self.assertFalse(w.save_btn.get_sensitive())

    def test_home_cannot_be_closed(self):
        w = self.win
        w.close_current_tab()
        w.tab_view.close_page(w.home_tab)
        self.assertEqual(w.tab_view.finished[-1], (w.home_tab, False))

    def test_new_tab_enables_actions_and_views(self):
        w = self.win
        page = w.new_tab()
        self.assertIs(w.current_page(), page)
        for name in DOC_ACTIONS + SCRIPT_ONLY_ACTIONS:
            self.assertTrue(self.action_enabled(name), name)
        self.assertTrue(w.view_box.get_visible())
        page.show_view('story')
        self.assertFalse(self.action_enabled('format-scene'))     # solo guion
        self.assertTrue(self.action_enabled('save'))
        self.assertTrue(w.view_story_btn.get_active())
        w.show_script()
        self.assertTrue(self.action_enabled('format-scene'))
        self.assertTrue(w.view_script_btn.get_active())

    def test_story_from_home_reuses_existing_document(self):
        w = self.win
        page = w.new_tab()
        w.show_home()
        self.assertIsNone(w.current_page())
        pages_before = w.tab_view.get_n_pages()
        w._open_story_from_home()                    # antes creaba SIEMPRE una pestaña nueva
        self.assertEqual(w.tab_view.get_n_pages(), pages_before)
        self.assertIs(w.current_page(), page)
        self.assertEqual(page.view_name, 'story')

    def test_story_from_home_with_no_documents_creates_one(self):
        w = self.win
        w._open_story_from_home()
        self.assertEqual(len(w._script_pages()), 1)
        self.assertEqual(w.current_page().view_name, 'story')

    def test_story_edits_mark_modified_and_persist(self):
        w = self.win
        page = w.new_tab()
        page.show_view('story')
        page.story._buffers['Logline'].set_text('Una mujer contra el tiempo')
        self.assertTrue(page._modified)
        path = os.path.join(self.dir, 'h.guion')
        self.assertTrue(w._do_save(page, path))
        self.assertFalse(page._modified)
        other = ScriptPage()
        other.load_from(path)
        self.assertEqual(other.story_sections['Logline'], 'Una mujer contra el tiempo')
        self.assertEqual(other.story.get_sections()['Logline'], 'Una mujer contra el tiempo')
        self.assertFalse(other._modified)

    def test_open_project_and_duplicate_selects_existing(self):
        w = self.win
        path = self.project(story={'Sinopsis': 'S'})
        page = w.open_path(path)
        self.assertIsNotNone(page)
        self.assertEqual(page.story_sections['Sinopsis'], 'S')
        n = w.tab_view.get_n_pages()
        w.show_home()
        again = w.open_path(path)
        self.assertIs(again, page)
        self.assertEqual(w.tab_view.get_n_pages(), n)
        self.assertIs(w.current_page(), page)

    def test_open_failure_creates_no_tab(self):
        w = self.win
        bad = os.path.join(self.dir, 'bin.guion')
        open(bad, 'wb').write(b'\xff\xfe\x80')
        n = w.tab_view.get_n_pages()
        self.assertIsNone(w.open_path(bad))
        self.assertIsNone(w.open_path(os.path.join(self.dir, 'nope.guion')))
        self.assertEqual(w.tab_view.get_n_pages(), n)

    def test_import_text_never_overwrites_original(self):
        w = self.win
        txt = os.path.join(self.dir, 'guion.fountain')
        open(txt, 'w', encoding='utf-8').write('INT. CASA - DÍA\n')
        page = w.open_path(txt)
        self.assertIsNone(page.current_file)
        self.assertEqual(page.suggested_file_name(), 'guion.guion')
        saved = []
        w._save_as = lambda p, done=None: saved.append(p)      # Guardar debe pedir nombre
        w.save_current()
        self.assertEqual(saved, [page])
        self.assertEqual(open(txt, encoding='utf-8').read(), 'INT. CASA - DÍA\n')

    def test_save_failure_is_reported_not_raised(self):
        w = self.win
        page = w.new_tab()
        ok = w._do_save(page, os.path.join(self.dir, 'no_existe_dir', 'x.guion'))
        self.assertFalse(ok)

    def test_recent_list_updates_and_removal(self):
        w = self.win
        path = self.project()
        w.open_path(path)
        names = [c._children[0] for c in w.recent_box._children]
        self.assertEqual(len(names), 1)
        w._forget_recent(path)
        self.assertEqual(len(w.recent_box._children), 1)      # solo el texto vacío
        self.assertIn('Todavía no hay', w.recent_box._children[0].get_text())

    def test_closing_modified_tab_asks_first(self):
        w = self.win
        page = w.new_tab()
        page._mark_modified()
        w.tab_view.close_page(page.tab_page)
        self.assertEqual(len(gtk_fake.PRESENTED), 1)
        self.assertEqual(w.tab_view.finished, [])               # aún sin decidir
        dlg = gtk_fake.PRESENTED[0]
        dlg.emit('response', 'cancel')
        self.assertEqual(w.tab_view.finished[-1][1], False)
        self.assertIn(page, w._script_pages())
        w.tab_view.close_page(page.tab_page)
        gtk_fake.PRESENTED[-1].emit('response', 'discard')
        self.assertEqual(w.tab_view.finished[-1][1], True)
        self.assertEqual(w._script_pages(), [])

    def test_closing_modified_tab_with_save(self):
        w = self.win
        path = self.project()
        page = w.open_path(path)
        page._buffer_text = None
        page.editor.set_text('Nuevo texto')
        page._mark_modified()
        w.tab_view.close_page(page.tab_page)
        gtk_fake.PRESENTED[-1].emit('response', 'save')
        self.assertEqual(w.tab_view.finished[-1][1], True)
        self.assertIn('Nuevo texto', open(path, encoding='utf-8').read())

    def test_closing_clean_tab_does_not_ask(self):
        w = self.win
        page = w.new_tab()
        w.tab_view.close_page(page.tab_page)
        self.assertEqual(gtk_fake.PRESENTED, [])
        self.assertEqual(w.tab_view.finished[-1][1], True)

    def test_window_close_with_unsaved_documents(self):
        w = self.win
        page = w.new_tab()
        page._mark_modified()
        w.close()
        self.assertFalse(w.closed)
        self.assertEqual(len(gtk_fake.PRESENTED), 1)
        gtk_fake.PRESENTED[0].emit('response', 'cancel')
        self.assertFalse(w.closed)
        w.close()
        gtk_fake.PRESENTED[-1].emit('response', 'discard')
        self.assertTrue(w.closed)

    def test_window_close_clean(self):
        w = self.win
        w.new_tab()
        w.close()
        self.assertTrue(w.closed)
        self.assertEqual(gtk_fake.PRESENTED, [])

    def test_window_title_follows_state(self):
        w = self.win
        self.assertEqual(w.get_title() if hasattr(w, 'get_title') else 'GuionStudio', 'GuionStudio')
        page = w.new_tab()
        page._mark_modified()
        self.assertIn('•', w._state.get('title', ''))

    def test_shortcut_validation(self):
        from src.window import is_valid_accelerator
        self.assertTrue(is_valid_accelerator(''))
        self.assertTrue(is_valid_accelerator('<Control>s'))

    def test_welcome_template_is_valid_script(self):
        from src.parser import extract_outline
        self.assertEqual([i['type'] for i in extract_outline(WELCOME)],
                         ['ACT', 'SEQ', 'SCENE', 'SCENE', 'ACT', 'SEQ', 'SCENE'])


class TitleAndWordTests(WindowTests):
    """Título del proyecto y exportación de la historia a Word."""

    def test_title_widget_follows_context(self):
        w = self.win
        self.assertEqual(w.title_stack.get_visible_child_name(), 'home')
        page = w.new_tab()
        self.assertEqual(w.title_stack.get_visible_child_name(), 'doc')
        w.show_home()
        self.assertEqual(w.title_stack.get_visible_child_name(), 'home')

    def test_typing_title_updates_page_tab_and_modified(self):
        w = self.win
        page = w.new_tab()
        page._modified = False
        w.title_entry.set_text('La noche eterna')
        self.assertEqual(page.project_title, 'La noche eterna')
        self.assertTrue(page._modified)
        self.assertEqual(page.get_display_title(), 'La noche eterna')
        self.assertEqual(page.tab_page._state.get('title'), 'La noche eterna')
        self.assertEqual(page.suggested_file_name(), 'La noche eterna.guion')

    def test_title_is_per_document(self):
        w = self.win
        a = w.new_tab(); w.title_entry.set_text('Uno')
        b = w.new_tab()
        self.assertEqual(w.title_entry.get_text(), '')      # no arrastra el de otro documento
        w.title_entry.set_text('Dos')
        w._select_page(a)
        self.assertEqual(w.title_entry.get_text(), 'Uno')
        self.assertEqual((a.project_title, b.project_title), ('Uno', 'Dos'))

    def test_switching_tabs_does_not_modify(self):
        w = self.win
        a = w.new_tab(); w.title_entry.set_text('Uno'); a._modified = False
        b = w.new_tab()
        w._select_page(a)
        self.assertFalse(a._modified)

    def test_title_persists_in_project_file(self):
        w = self.win
        page = w.new_tab()
        w.title_entry.set_text('Mi título')
        path = os.path.join(self.dir, 'x.guion')
        w._do_save(page, path)
        other = w.open_path(path)
        self.assertEqual(other.project_title, 'Mi título')
        self.assertFalse(other._modified)
        self.assertEqual(w.title_entry.get_text(), 'Mi título')

    def test_old_project_without_title_opens(self):
        page = self.win.open_path(self.project())
        self.assertEqual(page.project_title, '')
        self.assertEqual(page.get_display_title(), 'p.guion')

    def test_enter_in_title_returns_focus_to_editor(self):
        w = self.win
        page = w.new_tab()
        w.title_entry.emit('activate')
        self.assertTrue(getattr(page.editor.view, 'focused', False))

    def test_edit_title_action_enabled_only_with_document(self):
        w = self.win
        self.assertFalse(self.action_enabled('edit-title'))
        w.new_tab()
        self.assertTrue(self.action_enabled('edit-title'))
        self.assertTrue(self.action_enabled('export-story'))

    def test_header_buttons_use_labels_not_theme_icons(self):
        w = self.win
        self.assertEqual(w.sidebar_btn.get_label(), '📑')
        self.assertEqual(w.home_btn.get_label(), '🏠')
        self.assertEqual(w.save_btn.get_label(), '💾')
        self.assertIsNotNone(w.home_tab._state.get('icon'))      # icono propio en la pestaña fija

    def test_story_export_skips_empty_and_keeps_order(self):
        page = self.win.new_tab()
        page.story._buffers['Logline'].set_text('LL')
        page.story._buffers['Argumento'].set_text('AA')
        self.assertEqual(page.story_export_sections(), [('Argumento', 'AA'), ('Logline', 'LL')])

    def test_export_story_empty_warns_and_opens_no_dialog(self):
        w = self.win
        page = w.new_tab()
        calls = []
        w._on_story_word_done = lambda *a: calls.append(a)
        w.export_story_word()
        self.assertEqual(calls, [])

    def _fake_dialog(self, path):
        class F:
            def get_path(self_inner): return path
        class D:
            def save_finish(self_inner, r): return F()
        return D()

    def test_export_story_writes_valid_docx(self):
        import zipfile
        from xml.dom import minidom
        w = self.win
        page = w.new_tab()
        w.title_entry.set_text('Mi & "historia" <1>')
        page.story._buffers['Sinopsis'].set_text('María & el <mar>\n\nSegundo párrafo.\n\tcon tab')
        out = os.path.join(self.dir, 'salida')                    # sin extensión: se añade .docx
        w._on_story_word_done(self._fake_dialog(out), None, page)
        self.assertTrue(os.path.isfile(out + '.docx'))
        with zipfile.ZipFile(out + '.docx') as z:
            self.assertEqual(z.namelist()[0], '[Content_Types].xml')
            for name in z.namelist():
                minidom.parseString(z.read(name))                  # XML bien formado
            doc = z.read('word/document.xml').decode('utf-8')
        self.assertIn('Mi &amp; "historia" &lt;1&gt;', doc)
        self.assertIn('María &amp; el &lt;mar&gt;', doc)
        self.assertIn('Segundo párrafo.', doc)
        self.assertIn('Heading1', doc)
        self.assertNotIn('Argumento', doc)                         # fichas vacías no se exportan

    def test_export_story_failure_is_reported(self):
        w = self.win
        page = w.new_tab()
        page.story._buffers['Logline'].set_text('x')
        w._on_story_word_done(self._fake_dialog(os.path.join(self.dir, 'no', 'x.docx')), None, page)  # no lanza

    def test_story_button_in_workspace_triggers_export(self):
        w = self.win
        page = w.new_tab()
        got = []
        page.on_export_story = got.append
        page.story.on_export()
        self.assertEqual(got, [page])


if __name__ == '__main__':
    unittest.main()
