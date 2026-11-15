# icons.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Iconos propios incrustados.

Los iconos del tema (go-home-symbolic, sidebar-show-symbolic…) no existen en
todos los sistemas y se veían en blanco. Este se dibuja siempre igual.
"""

import base64

HOME_PNG_B64 = (
    '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'
)


def home_icon_bytes():
    return base64.b64decode(HOME_PNG_B64)
