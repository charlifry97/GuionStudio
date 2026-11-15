# main.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import json
from pathlib import Path
import gi

from gettext import gettext as _

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw, GLib
from .window import GuionstudioWindow, is_valid_accelerator


class GuionstudioApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='io.github.charlifry97.GuionStudio',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/io/github/charlifry97/GuionStudio')

        self.create_action('quit', self.on_quit_action, ['<control>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action)

        # Atajos de archivo
        self.set_accels_for_action('win.new', ['<Control>n'])
        self.set_accels_for_action('win.open', ['<Control>o'])
        self.set_accels_for_action('win.save', ['<Control>s'])
        self.set_accels_for_action('win.save-as', ['<Control><Shift>s'])
        self.set_accels_for_action('win.export', ['<Control>e'])
        self.set_accels_for_action('win.close-tab', ['<Control>w'])
        self.set_accels_for_action('win.home', ['<Alt>Home'])
        self.set_accels_for_action('win.export-story', ['<Control><Shift>e'])
        self.set_accels_for_action('win.edit-title', ['F2'])
        self.set_accels_for_action('win.view-script', ['<Control><Shift>g'])
        self.set_accels_for_action('win.view-story', ['<Control><Shift>h'])

        # Atajos de formato
        self.set_accels_for_action('win.format-action', ['<Control>1'])
        self.set_accels_for_action('win.format-scene', ['<Control>2'])
        self.set_accels_for_action('win.format-character', ['<Control>3'])
        self.set_accels_for_action('win.format-dialogue', ['<Control>4'])
        self.set_accels_for_action('win.format-parenthetical', ['<Control>5'])
        self.set_accels_for_action('win.format-transition', ['<Control>6'])
        self.set_accels_for_action('win.format-act', ['<Control>7'])
        self.set_accels_for_action('win.format-seq', ['<Control>8'])
        self.set_accels_for_action('win.highlight-apply', ['<Control><Alt>h'])
        self.set_accels_for_action('win.highlight-clear', ['<Control><Alt>b'])
        self.set_accels_for_action('win.highlight-filter-1', ['<Control><Alt>1'])
        self.set_accels_for_action('win.highlight-filter-2', ['<Control><Alt>2'])
        self.set_accels_for_action('win.highlight-filter-3', ['<Control><Alt>3'])
        self.set_accels_for_action('win.highlight-filter-4', ['<Control><Alt>4'])
        self.set_accels_for_action('win.highlight-show-all', ['<Control><Alt>0'])
        shortcut_file = Path(GLib.get_user_config_dir()) / 'guionstudio' / 'shortcuts.json'
        try:
            custom = json.loads(shortcut_file.read_text(encoding='utf-8')) if shortcut_file.exists() else {}
            if not isinstance(custom, dict):
                custom = {}
            for action, accel in custom.items():
                if isinstance(action, str) and isinstance(accel, str) and is_valid_accelerator(accel):
                    self.set_accels_for_action(action, [accel] if accel else [])
        except (OSError, ValueError):
            pass

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = GuionstudioWindow(application=self)
        win.present()

    def on_quit_action(self, *args):
        # Cerrar la ventana (y no app.quit() directamente) permite que
        # pregunte por los documentos con cambios sin guardar.
        win = self.props.active_window
        if win:
            win.close()
        else:
            self.quit()

    def on_about_action(self, *args):
        about = Adw.AboutDialog(application_name='GuionStudio',
                                application_icon='io.github.charlifry97.GuionStudio',
                                developer_name='Carlos A. Rguez Padrón',
                                version='1.4.1',
                                translator_credits=_('translator-credits'),
                                developers=['Carlos A. Rguez Padrón'],
                                copyright='© 2026 Carlos A. Rguez Padrón')
        about.present(self.props.active_window)

    def on_preferences_action(self, widget, _):
        print('app.preferences action activated')

    def create_action(self, name, callback, shortcuts=None):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    app = GuionstudioApplication()
    return app.run(sys.argv)
