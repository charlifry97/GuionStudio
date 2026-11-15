pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'guionstudio'
gnome = import('gnome')

gnome.compile_resources('guionstudio',
  'guionstudio.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'guionstudio.in',
  output: 'guionstudio',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

guionstudio_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'script_page.py',
  'parser.py',
  'editor.py',
  'structure_panel.py',
  'exporter.py',
  'story_memory.py',
  'story_workspace.py',
  'project_io.py',
  'docx_export.py',
  'pdf_export.py',
  'icons.py',
]
install_data(guionstudio_sources, install_dir: moduledir)
