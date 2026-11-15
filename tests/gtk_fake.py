"""GTK 4 / libadwaita simulados para ejecutar el código de GuionStudio sin GTK.

No sustituye a una prueba en un escritorio real, pero permite ejecutar la
lógica de interfaz y del editor y detectar errores de nombres, flujo y datos.
El TextBuffer imita la semántica documentada de GTK (iteradores, etiquetas,
marcas, forward_to_line_end que salta a la línea siguiente, etc.).
"""
import itertools
import os
import sys
import tempfile
import types

_flag_counter = itertools.count(1)
_flags = {}


def _flag(key):
    if key not in _flags:
        _flags[key] = 1 << (next(_flag_counter) % 60)
    return _flags[key]


class Meta(type):
    def __getattr__(cls, name):
        if name.startswith('__'):
            raise AttributeError(name)
        if name.startswith('new'):
            return lambda *a, **k: cls(**{kk: vv for kk, vv in k.items()})
        if name[:1].isupper() or name.startswith('KEY_'):
            return _flag((cls.__name__, name))
        return lambda *a, **k: None


class Widget(metaclass=Meta):
    def __init__(self, *args, **kwargs):
        self._props = dict(kwargs)
        self._children = []
        self._handlers = {}
        self._classes = set()
        self._parent = None
        self._state = {}
        if 'label' in kwargs:
            self._state['text'] = kwargs['label']
        if 'text' in kwargs:
            self._state['text'] = kwargs['text']
        self._state['visible'] = True
        self._state['editable'] = True
        self._state['sensitive'] = True
        self._state['enabled'] = True

    # señales
    def connect(self, sig, cb, *args):
        self._handlers.setdefault(sig, []).append((cb, args))
        return len(self._handlers[sig])

    def emit(self, sig, *a):
        for cb, args in list(self._handlers.get(sig, [])):
            cb(self, *a, *args)

    # jerarquía
    def append(self, child):
        self._children.append(child)
        child._parent = self

    def prepend(self, child):
        self._children.insert(0, child)
        child._parent = self

    def remove(self, child):
        self._children.remove(child)
        child._parent = None

    def insert_child_after(self, child, sibling):
        index = 0 if sibling is None else self._children.index(sibling) + 1
        self._children.insert(index, child)
        child._parent = self

    def get_first_child(self):
        return self._children[0] if self._children else None

    def get_prev_sibling(self):
        if self._parent and self in self._parent._children:
            i = self._parent._children.index(self)
            return self._parent._children[i - 1] if i else None
        return None

    def get_parent(self):
        return self._state.get('parent', self._parent)

    def set_parent(self, p):
        self._state['parent'] = p

    def set_child(self, c):
        self._state['child'] = c
        self._children = [c]

    def get_child(self):
        return self._state.get('child')

    def set_start_child(self, c):
        self._state['start'] = c

    def set_end_child(self, c):
        self._state['end'] = c

    def set_content(self, c):
        self._state['content'] = c

    def add_top_bar(self, c):
        self._children.append(c)

    # css / estado
    def add_css_class(self, c):
        self._classes.add(c)

    def remove_css_class(self, c):
        self._classes.discard(c)

    def has_css_class(self, c):
        return c in self._classes

    def set_text(self, v):
        self._state['text'] = v

    def set_label(self, v):
        self._state['text'] = v

    def get_text(self):
        return self._state.get('text', '')

    def get_label(self):
        return self._state.get('text', '')

    def get_active(self):
        return self._state.get('active', False)

    def set_active(self, v):
        v = bool(v)
        changed = self._state.get('active', False) != v
        self._state['active'] = v
        if changed:
            self.emit('toggled')

    def get_visible(self):
        return self._state['visible']

    def set_visible(self, v):
        self._state['visible'] = v

    def popup(self):
        self._state['visible'] = True

    def popdown(self):
        self._state['visible'] = False

    def get_editable(self):
        return self._state['editable']

    def set_editable(self, v):
        self._state['editable'] = v

    def set_sensitive(self, v):
        self._state['sensitive'] = v

    def get_sensitive(self):
        return self._state['sensitive']

    def set_enabled(self, v):
        self._state['enabled'] = v

    def get_enabled(self):
        return self._state['enabled']

    def get_vadjustment(self):
        return Adjustment()

    def get_selected(self):
        return self._state.get('selected', 0)

    def get_root(self):
        return None

    def get_display(self):
        return None

    def __getattr__(self, name):
        if name.startswith('__') or name.startswith('_'):
            raise AttributeError(name)
        if name.startswith('set_'):
            key = name[4:]
            return lambda *a, **k: self._state.__setitem__(key, a[0] if a else None)
        if name.startswith('get_'):
            key = name[4:]
            return lambda *a, **k: self._state.get(key)
        return lambda *a, **k: None


class Adjustment(Widget):
    def get_value(self):
        return 0

    def set_value(self, v):
        pass


class ListBox(Widget):
    def get_row_at_index(self, i):
        return self._children[i] if 0 <= i < len(self._children) else None

    def select_row(self, row):
        self._selected = row
        self.emit('row-selected', row)

    def get_selected_row(self):
        return getattr(self, '_selected', None)


class ListBoxRow(Widget):
    def get_index(self):
        return self._parent._children.index(self)


class TabPage(Widget):
    def __init__(self, child):
        super().__init__()
        self._child = child

    def get_child(self):
        return self._child


class TabView(Widget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.pages = []
        self.selected = None
        self.finished = []
        self.pinned = set()

    def append(self, child):
        page = TabPage(child)
        self.pages.append(page)
        if self.selected is None:
            self.selected = page
            self.emit('notify::selected-page', None)
        return page

    def get_n_pages(self):
        return len(self.pages)

    def get_nth_page(self, i):
        return self.pages[i]

    def get_selected_page(self):
        return self.selected

    def set_selected_page(self, p):
        if p is not self.selected:
            self.selected = p
            self.emit('notify::selected-page', None)

    def set_page_pinned(self, p, v):
        self.pinned.add(p)

    def close_page(self, page):
        self.emit('close-page', page)

    def close_page_finish(self, page, confirm):
        self.finished.append((page, confirm))
        if confirm and page in self.pages:
            self.pages.remove(page)
            if self.selected is page:
                self.selected = self.pages[-1] if self.pages else None
                self.emit('notify::selected-page', None)


class Stack(Widget):
    def add_named(self, child, name):
        self._children.append(child)
        self._state.setdefault('named', {})[name] = child
        self._state.setdefault('visible_name', name)

    def set_visible_child_name(self, n):
        self._state['visible_name'] = n

    def get_visible_child_name(self):
        return self._state.get('visible_name')


class Popover(Widget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._state['visible'] = False


class DropDown(Widget):
    def set_model(self, m):
        self._state['model'] = m
        self._state['selected'] = 0
        self.emit('notify::selected', None)

    def set_selected(self, i):
        self._state['selected'] = i
        self.emit('notify::selected', None)


class Entry(Widget):
    def set_text(self, v):
        changed = self._state.get('text') != v
        self._state['text'] = v
        if changed:
            self.emit('changed')


class Rect:
    x = y = width = height = 0


class Tag:
    def __init__(self, name):
        self.name = name
        self.props = {}

    def set_property(self, k, v):
        self.props[k] = v


class FakeIter:
    def __init__(self, buf, off):
        self.buf = buf
        self.off = max(0, min(off, len(buf.text)))

    def get_offset(self):
        return self.off

    def copy(self):
        return FakeIter(self.buf, self.off)

    def _line_start(self):
        return self.buf.text.rfind('\n', 0, self.off) + 1

    def set_line_offset(self, n):
        self.off = self._line_start() + n

    def starts_line(self):
        return self.off == 0 or self.buf.text[self.off - 1] == '\n'

    def ends_line(self):
        return self.off == len(self.buf.text) or self.buf.text[self.off] == '\n'

    def forward_to_line_end(self):
        """Semántica documentada de GTK: si ya está al final de una línea,
        pasa al final de la SIGUIENTE."""
        text = self.buf.text
        if self.ends_line():
            if self.off >= len(text):
                return False
            nxt = text.find('\n', self.off + 1)
            self.off = len(text) if nxt < 0 else nxt
            return True
        nxt = text.find('\n', self.off)
        self.off = len(text) if nxt < 0 else nxt
        return True

    def backward_chars(self, n):
        self.off = max(0, self.off - n)
        return True

    def forward_chars(self, n):
        self.off = min(len(self.buf.text), self.off + n)
        return True

    def _tagged(self, tag, off):
        return 0 <= off < len(self.buf.text) and off in self.buf.applied.get(tag.name, set())

    def has_tag(self, tag):
        return self._tagged(tag, self.off)

    def starts_tag(self, tag):
        return self._tagged(tag, self.off) and not self._tagged(tag, self.off - 1)

    def ends_tag(self, tag):
        return self._tagged(tag, self.off - 1) and not self._tagged(tag, self.off)

    def forward_to_tag_toggle(self, tag):
        for o in range(self.off + 1, len(self.buf.text) + 1):
            before, after = self._tagged(tag, o - 1), self._tagged(tag, o)
            if before != after and o < len(self.buf.text):
                self.off = o
                return True
        self.off = len(self.buf.text)
        return False


class Mark:
    def __init__(self, off, left):
        self.off = off
        self.left = left


class TextBuffer(Widget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.text = ''
        self.tags = {}
        self.applied = {}
        self.marks = {'insert': Mark(0, False), 'selection_bound': Mark(0, True)}
        self.undo_log = []

    # señales de cambio
    def _changed(self):
        self.emit('changed')

    def get_start_iter(self):
        return FakeIter(self, 0)

    def get_end_iter(self):
        return FakeIter(self, len(self.text))

    def get_iter_at_offset(self, off):
        return FakeIter(self, off)

    def get_iter_at_line(self, line):
        lines = self.text.split('\n')
        return True, FakeIter(self, sum(len(l) + 1 for l in lines[:line]))

    def get_line_count(self):
        return self.text.count('\n') + 1

    def get_char_count(self):
        return len(self.text)

    def get_text(self, s, e, include):
        return self.text[s.off:e.off]

    def set_text(self, text):
        self.text = text
        self.applied = {}
        for m in self.marks.values():
            m.off = min(m.off, len(text))
        self._changed()

    def insert(self, it, text):
        pos = it.off
        self.text = self.text[:pos] + text + self.text[pos:]
        n = len(text)
        for name, offs in self.applied.items():
            self.applied[name] = {o + n if o >= pos else o for o in offs}
        for m in self.marks.values():
            if m.off > pos or (m.off == pos and not m.left):
                m.off += n
        it.off = pos + n
        self._changed()

    def delete(self, s, e):
        a, b = s.off, e.off
        self.text = self.text[:a] + self.text[b:]
        n = b - a
        for name, offs in self.applied.items():
            self.applied[name] = {(o - n if o >= b else o) for o in offs if not (a <= o < b)}
        for m in self.marks.values():
            if m.off >= b:
                m.off -= n
            elif m.off > a:
                m.off = a
        e.off = s.off = a
        self._changed()

    # etiquetas
    def create_tag(self, name):
        tag = Tag(name)
        self.tags[name] = tag
        self.applied[name] = set()
        return tag

    def get_tag_table(self):
        outer = self

        class Table:
            @staticmethod
            def lookup(name):
                return outer.tags.get(name)
        return Table()

    def apply_tag_by_name(self, name, s, e):
        self.applied.setdefault(name, set()).update(range(s.off, e.off))

    def remove_tag_by_name(self, name, s, e):
        if name in self.applied:
            self.applied[name] -= set(range(s.off, e.off))

    def remove_tag(self, tag, s, e):
        self.remove_tag_by_name(tag.name, s, e)

    # marcas / cursor
    def get_insert(self):
        return self.marks['insert']

    def get_iter_at_mark(self, mark):
        return FakeIter(self, mark.off)

    def place_cursor(self, it):
        self.marks['insert'].off = it.off
        self.marks['selection_bound'].off = it.off

    def select_range(self, ins, bound):
        self.marks['insert'].off = ins.off
        self.marks['selection_bound'].off = bound.off

    def get_selection_bounds(self):
        a, b = self.marks['insert'].off, self.marks['selection_bound'].off
        if a == b:
            return ()
        lo, hi = sorted((a, b))
        return FakeIter(self, lo), FakeIter(self, hi)

    def create_mark(self, name, it, left):
        m = Mark(it.off, left)
        self.marks[name or object()] = m
        return m

    def move_mark(self, mark, it):
        mark.off = it.off

    def begin_user_action(self):
        pass

    def end_user_action(self):
        pass

    def begin_irreversible_action(self):
        self.undo_log.append('begin_irreversible')

    def end_irreversible_action(self):
        pass


class TextView(Widget):
    def __init__(self, buffer=None, **k):
        super().__init__(**k)
        self._buffer = buffer if buffer is not None else TextBuffer()
        self.scrolled_to = []

    def get_buffer(self):
        return self._buffer

    def set_buffer(self, b):
        self._buffer = b

    def get_iter_location(self, it):
        return Rect()

    def buffer_to_window_coords(self, t, x, y):
        return x, y

    def scroll_to_mark(self, mark, *a):
        self.scrolled_to.append(mark.off)

    def grab_focus(self):
        self.focused = True


class Button(Widget):
    pass


class SimpleAction(Widget):
    def __init__(self, name=None, **k):
        super().__init__(**k)
        self.name = name

    @staticmethod
    def new(name, param):
        return SimpleAction(name)


class ApplicationWindow(Widget):
    def __init__(self, **k):
        super().__init__(**k)
        self.actions = {}
        self.closed = False

    def add_action(self, a):
        self.actions[a.name] = a

    def lookup_action(self, name):
        return self.actions.get(name)

    def close(self):
        self.closed = True
        for cb, args in self._handlers.get('close-request', []):
            if cb(self, *args):
                self.closed = False
                return
        self.closed = True


class Menu:
    def __init__(self, *a, **k):
        self.items = []

    def append(self, *a):
        self.items.append(a)

    def append_section(self, *a):
        self.items.append(a)

    def append_submenu(self, *a):
        self.items.append(a)


PRESENTED = []


class AlertDialog(Widget):
    @staticmethod
    def new(heading, body):
        d = AlertDialog()
        d.heading, d.body, d.responses = heading, body, []
        return d

    def add_response(self, rid, label):
        self.responses.append(rid)

    def present(self, parent=None):
        PRESENTED.append(self)


class GLibError(Exception):
    def __init__(self, message='', code=0):
        super().__init__(message)
        self.message = message

    def matches(self, quark, code):
        return False


class Bytes:
    @staticmethod
    def new(data):
        return data


class FakeGLib(types.ModuleType):
    def __init__(self):
        super().__init__('GLib')
        self.timeouts = {}
        self._ids = itertools.count(1)
        self.config_dir = tempfile.mkdtemp(prefix='guion-test-')
        self.Error = GLibError
        self.Bytes = Bytes

    def timeout_add(self, ms, cb, *a):
        i = next(self._ids)
        self.timeouts[i] = cb
        return i

    def idle_add(self, cb, *a):
        return self.timeout_add(0, cb)

    def source_remove(self, i):
        self.timeouts.pop(i, None)

    def run_timeouts(self):
        for i, cb in list(self.timeouts.items()):
            self.timeouts.pop(i, None)
            cb()

    def get_user_config_dir(self):
        return self.config_dir


class FakeModule(types.ModuleType):
    EXPLICIT = {}

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        if name in self.EXPLICIT:
            return self.EXPLICIT[name]
        if name[:1].isupper():
            cls = Meta(name, (Widget,), {})
            setattr(self, name, cls)
            return cls
        if name.startswith('KEY_'):
            return _flag(('KEY', name))
        return lambda *a, **k: (True, 0, 0) if name == 'accelerator_parse' else None


def install():
    glib = FakeGLib()

    gtk = FakeModule('Gtk')
    gtk.EXPLICIT = {
        'TextBuffer': TextBuffer, 'TextView': TextView, 'ListBox': ListBox,
        'ListBoxRow': ListBoxRow, 'Stack': Stack, 'Popover': Popover,
        'DropDown': DropDown, 'Entry': Entry, 'Button': Button,
    }
    adw = FakeModule('Adw')
    adw.EXPLICIT = {'TabView': TabView, 'ApplicationWindow': ApplicationWindow,
                    'AlertDialog': AlertDialog}
    gdk = FakeModule('Gdk')
    gdk.EXPLICIT = {'Rectangle': Rect}
    gio = FakeModule('Gio')
    gio.EXPLICIT = {'SimpleAction': SimpleAction, 'Menu': Menu}
    pango = FakeModule('Pango')

    repo = types.ModuleType('gi.repository')
    repo.Gtk, repo.Adw, repo.Gdk, repo.Gio, repo.Pango, repo.GLib = gtk, adw, gdk, gio, pango, glib
    gi = types.ModuleType('gi')
    gi.require_version = lambda *a, **k: None
    gi.repository = repo
    sys.modules['gi'] = gi
    sys.modules['gi.repository'] = repo
    return glib
