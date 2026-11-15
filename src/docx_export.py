# docx_export.py
#
# Copyright 2026 Carlos
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Exportación a Word (.docx) sin dependencias externas.

Un .docx es un ZIP con varios XML. Aquí se genera el conjunto mínimo y
válido: tipos de contenido, relaciones, estilos (Título, Título 1, Normal,
y los estilos de guion), el documento y las propiedades. A4 con 2,5 cm.
"""

import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

_INVALID_XML = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]')

FONT = 'Times New Roman'

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
    '</Types>'
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
    '</Relationships>'
)

_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '</Relationships>'
)

_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults>'
    f'<w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT}" w:cs="{FONT}"/>'
    '<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="es-ES" w:eastAsia="es-ES" w:bidi="ar-SA"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
    '</w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
    '<w:next w:val="Normal"/><w:qFormat/>'
    '<w:pPr><w:keepNext/><w:spacing w:before="0" w:after="120"/><w:jc w:val="center"/></w:pPr>'
    f'<w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/><w:b/><w:bCs/><w:sz w:val="48"/><w:szCs w:val="48"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/>'
    '<w:next w:val="Normal"/><w:qFormat/>'
    '<w:pPr><w:spacing w:before="0" w:after="480"/><w:jc w:val="center"/></w:pPr>'
    f'<w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/><w:i/><w:iCs/><w:color w:val="595959"/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
    '<w:next w:val="Normal"/><w:qFormat/>'
    '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="360" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>'
    f'<w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/><w:b/><w:bCs/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>'
    # ── Estilos de guion (formato editorial estándar) ──
    '<w:style w:type="paragraph" w:styleId="ScriptAct"><w:name w:val="Script Act"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:jc w:val="center"/><w:spacing w:before="480" w:after="240"/></w:pPr>'
    '<w:rPr><w:b/><w:bCs/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="ScriptSeq"><w:name w:val="Script Sequence"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:jc w:val="center"/><w:spacing w:before="360" w:after="180"/></w:pPr>'
    '<w:rPr><w:b/><w:bCs/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="ScriptScene"><w:name w:val="Script Scene"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:spacing w:before="360" w:after="120"/></w:pPr>'
    '<w:rPr><w:b/><w:bCs/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="ScriptCharacter"><w:name w:val="Script Character"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:ind w:left="3600"/><w:spacing w:before="200" w:after="0"/></w:pPr>'
    '<w:rPr><w:b/><w:bCs/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="ScriptParenthetical"><w:name w:val="Script Parenthetical"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:ind w:left="2880" w:right="1440"/></w:pPr>'
    '<w:rPr><w:i/><w:iCs/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="ScriptDialogue"><w:name w:val="Script Dialogue"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:ind w:left="2160" w:right="1440"/><w:spacing w:after="120"/></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="ScriptTransition"><w:name w:val="Script Transition"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:jc w:val="right"/><w:spacing w:before="120"/></w:pPr>'
    '<w:rPr><w:b/><w:bCs/></w:rPr></w:style>'
    '</w:styles>'
)


def _clean(text):
    return _INVALID_XML.sub('', text)


def _runs(line):
    parts = line.split('\t')
    out = []
    for index, part in enumerate(parts):
        if index:
            out.append('<w:r><w:tab/></w:r>')
        if part:
            out.append(f'<w:r><w:t xml:space="preserve">{escape(part)}</w:t></w:r>')
    return ''.join(out)


def _paragraph(text, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    return f'<w:p>{ppr}{_runs(_clean(text))}</w:p>'


def build_document_xml(title, subtitle, sections):
    body = []
    if title:
        body.append(_paragraph(title, 'Title'))
    if subtitle:
        body.append(_paragraph(subtitle, 'Subtitle'))
    for heading, text in sections:
        body.append(_paragraph(heading, 'Heading1'))
        lines = _clean(text).replace('\r\n', '\n').replace('\r', '\n').split('\n')
        for line in lines:
            if line.strip():
                body.append(_paragraph(line))
    body.append(
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" '
        'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + ''.join(body) + '</w:body></w:document>'
    )


def build_docx(title, sections, subtitle='', author=''):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{escape(_clean(title or ""))}</dc:title>'
        f'<dc:creator>{escape(_clean(author or "GuionStudio"))}</dc:creator>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        '</cp:coreProperties>'
    )
    app = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        '<Application>GuionStudio</Application></Properties>'
    )
    import io
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', _CONTENT_TYPES)
        archive.writestr('_rels/.rels', _ROOT_RELS)
        archive.writestr('word/document.xml', build_document_xml(title, subtitle, sections))
        archive.writestr('word/_rels/document.xml.rels', _DOC_RELS)
        archive.writestr('word/styles.xml', _STYLES)
        archive.writestr('docProps/core.xml', core)
        archive.writestr('docProps/app.xml', app)
    return buffer.getvalue()


def write_docx(path, title, sections, subtitle='', author=''):
    data = build_docx(title, sections, subtitle, author)
    _atomic_write(path, data)


# ─────────────────────── EXPORTACIÓN DE GUION ───────────────────────

def build_script_document_xml(text, title='Guion'):
    from .parser import classify
    body = []
    if title:
        body.append(_paragraph(title, 'Title'))
    lines = text.split('\n')
    classes = [c for _, _, c in classify(text)]
    style_map = {
        'ACT': 'ScriptAct', 'SEQ': 'ScriptSeq', 'SCENE': 'ScriptScene',
        'CHARACTER': 'ScriptCharacter', 'DIALOGUE': 'ScriptDialogue',
        'PARENTHETICAL': 'ScriptParenthetical', 'TRANSITION': 'ScriptTransition',
    }
    for line, cls in zip(lines, classes):
        stripped = line.strip()
        if not stripped:
            body.append('<w:p/>')
            continue
        style = style_map.get(cls)
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
        body.append(f'<w:p>{ppr}{_runs(_clean(stripped))}</w:p>')
    body.append(
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" '
        'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + ''.join(body) + '</w:body></w:document>'
    )


def build_script_docx(text, title='Guion', author='GuionStudio'):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{escape(_clean(title or ""))}</dc:title>'
        f'<dc:creator>{escape(_clean(author or "GuionStudio"))}</dc:creator>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        '</cp:coreProperties>'
    )
    app = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        '<Application>GuionStudio</Application></Properties>'
    )
    import io
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', _CONTENT_TYPES)
        archive.writestr('_rels/.rels', _ROOT_RELS)
        archive.writestr('word/document.xml', build_script_document_xml(text, title))
        archive.writestr('word/_rels/document.xml.rels', _DOC_RELS)
        archive.writestr('word/styles.xml', _STYLES)
        archive.writestr('docProps/core.xml', core)
        archive.writestr('docProps/app.xml', app)
    return buffer.getvalue()


def write_script_docx(path, text, title='Guion'):
    _atomic_write(path, build_script_docx(text, title))


def _atomic_write(path, data):
    path = os.path.realpath(path)
    directory = os.path.dirname(path) or '.'
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix='.guion-', suffix='.tmp')
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
        return
    except OSError:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except OSError: pass
    with open(path, 'wb') as handle:
        handle.write(data)
