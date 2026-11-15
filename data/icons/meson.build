application_id = 'io.github.charlifry97.GuionStudio'

scalable_dir = 'hicolor' / 'scalable' / 'apps'
install_data(
  scalable_dir / ('@0@.svg').format(application_id),
  install_dir: get_option('datadir') / 'icons' / scalable_dir
)

symbolic_dir = 'hicolor' / 'symbolic' / 'apps'
install_data(
  symbolic_dir / ('@0@-symbolic.svg').format(application_id),
  install_dir: get_option('datadir') / 'icons' / symbolic_dir
)

# High-resolution raster fallback for desktops that prefer PNG icons.
install_data(
  'hicolor' / '512x512' / 'apps' / ('@0@.png').format(application_id),
  install_dir: get_option('datadir') / 'icons' / 'hicolor' / '512x512' / 'apps'
)
