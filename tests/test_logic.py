"""Pruebas de lógica pura (sin GTK): parser, E/S de proyectos, recientes."""
import json
import os
import tempfile
import time
import unittest

from src.parser import (extract_outline, outline_move_flags, move_outline_spans,
                        move_outline_block, remap_ranges_after_swap, find_occurrence,
                        normalize_structural_case, classify, extract_characters)
from src.project_io import (read_project, write_project, load_recent, add_recent,
                            remove_recent, safe_file_stem)
from src.docx_export import build_docx, build_document_xml

TEXT = ("# ACTO 1\nA\n## SECUENCIA 1\nB\nINT. CASA - DÍA\nC\nINT. CALLE - NOCHE\nD\n"
        "## SECUENCIA 2\nE\nEXT. PARQUE - DÍA\nF\n# ACTO 2\nG\nINT. FINAL - NOCHE\nH\n")


class ParserTests(unittest.TestCase):
    def test_move_flags_match_move_function(self):
        outline = extract_outline(TEXT)
        flags = outline_move_flags(outline)
        for i in range(len(outline)):
            for d, idx in ((-1, 0), (1, 1)):
                possible = move_outline_block(TEXT, outline, i, d) is not None
                self.assertEqual(flags[i][idx], possible, (i, d))

    def test_outline_line_numbers(self):
        for item in extract_outline(TEXT):
            self.assertEqual(TEXT.split('\n')[item['line'] - 1].strip(), item['text'])

    def test_classified_reuse_equals_fresh(self):
        c = classify(TEXT)
        self.assertEqual(extract_outline(TEXT, c), extract_outline(TEXT))

    def test_remap_ranges(self):
        spans = move_outline_spans(TEXT, extract_outline(TEXT), 2, 1)
        a0, a1, b0, b1 = spans
        moved = move_outline_block(TEXT, extract_outline(TEXT), 2, 1)
        # Un rango sobre "C" (acción de la escena 1) debe seguir sobre "C".
        c = TEXT.index('\nC\n') + 1
        (new_a, new_b), = remap_ranges_after_swap([(c, c + 1)], spans)
        self.assertEqual(moved[new_a:new_b], 'C')
        d = TEXT.index('\nD\n') + 1
        (na, nb), = remap_ranges_after_swap([(d, d + 1)], spans)
        self.assertEqual(moved[na:nb], 'D')
        # Fuera de la región no cambia.
        (x, y), = remap_ranges_after_swap([(0, 3)], spans)
        self.assertEqual((x, y), (0, 3))

    def test_find_occurrence_wraps_and_whole_word(self):
        t = "Ana habla. BANANA. ana vuelve."
        self.assertEqual(find_occurrence(t, 'ANA', 0), (0, 3))
        self.assertEqual(find_occurrence(t, 'ANA', 1), (19, 3))   # salta BANANA
        self.assertEqual(find_occurrence(t, 'ANA', 20), (0, 3))   # da la vuelta
        self.assertIsNone(find_occurrence(t, 'LUIS', 0))
        self.assertIsNone(find_occurrence(t, '  ', 0))

    def test_normalize_is_linear_enough(self):
        big = "\n\n".join(f"María{i % 7}\nHola número {i}." for i in range(3000))
        start = time.time()
        normalize_structural_case(big)
        self.assertLess(time.time() - start, 3.0)

    def test_characters_unchanged(self):
        self.assertEqual(extract_characters("\nMARÍA\nHola\n"), ['MARÍA'])


class ProjectIOTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def p(self, name):
        return os.path.join(self.dir, name)

    def test_roundtrip(self):
        path = self.p('a.guion')
        write_project(path, {'content': 'ñandú', 'story_sections': {'Logline': 'x'}, 'highlights': {}})
        data = read_project(path)
        self.assertTrue(data['is_project'])
        self.assertEqual(data['content'], 'ñandú')
        self.assertEqual(data['story_sections'], {'Logline': 'x'})
        self.assertEqual([f for f in os.listdir(self.dir) if f.endswith('.tmp')], [])

    def test_text_import_is_not_a_project(self):
        path = self.p('a.fountain')
        open(path, 'w', encoding='utf-8').write('INT. CASA - DÍA\n')
        data = read_project(path)
        self.assertFalse(data['is_project'])
        self.assertEqual(data['content'], 'INT. CASA - DÍA\n')

    def test_broken_json_guion_opens_as_text_and_flags_notice(self):
        path = self.p('roto.guion')
        open(path, 'w', encoding='utf-8').write('{"content": "abc"')
        data = read_project(path)
        self.assertFalse(data['is_project'])
        self.assertTrue(data['notice'])

    def test_wrong_shape_json(self):
        for raw in ('[1,2]', '{"content": 5}', '"hola"'):
            path = self.p('x.guion')
            open(path, 'w', encoding='utf-8').write(raw)
            self.assertFalse(read_project(path)['is_project'], raw)

    def test_bad_story_sections_are_filtered(self):
        path = self.p('s.guion')
        json.dump({'content': 'a', 'story_sections': {'Logline': 3, 'Sinopsis': 'ok'}, 'highlights': []},
                  open(path, 'w'))
        data = read_project(path)
        self.assertEqual(data['story_sections'], {'Sinopsis': 'ok'})
        self.assertEqual(data['highlights'], {})

    def test_binary_raises_valueerror(self):
        path = self.p('b.guion')
        open(path, 'wb').write(b'\xff\xfe\x00\x80')
        with self.assertRaises(ValueError):
            read_project(path)

    def test_missing_raises_oserror(self):
        with self.assertRaises(OSError):
            read_project(self.p('no.guion'))

    def test_write_preserves_permissions_and_original_on_failure(self):
        path = self.p('m.guion')
        write_project(path, {'content': 'uno'})
        os.chmod(path, 0o640)
        write_project(path, {'content': 'dos'})
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o640)
        with self.assertRaises(TypeError):
            write_project(path, {'content': object()})
        self.assertEqual(read_project(path)['content'], 'dos')   # intacto
        self.assertEqual([f for f in os.listdir(self.dir) if f.endswith('.tmp')], [])

    def test_recent_list(self):
        rf = self.p('cfg/recent.json')
        files = []
        for i in range(10):
            f = self.p(f'f{i}.guion')
            open(f, 'w').write('{}')
            files.append(f)
            add_recent(rf, f)
        recent = load_recent(rf)
        self.assertEqual(len(recent), 8)
        self.assertEqual(recent[0], files[-1])
        add_recent(rf, files[5])
        self.assertEqual(load_recent(rf)[0], files[5])
        self.assertEqual(len(set(load_recent(rf))), len(load_recent(rf)))
        os.unlink(files[5])
        self.assertNotIn(files[5], load_recent(rf))
        remove_recent(rf, files[9])
        self.assertNotIn(files[9], load_recent(rf))

    def test_recent_survives_corrupt_file(self):
        rf = self.p('recent.json')
        open(rf, 'w').write('no es json')
        self.assertEqual(load_recent(rf), [])
        f = self.p('x.guion'); open(f, 'w').write('{}')
        self.assertEqual(add_recent(rf, f), [f])


class TitleAndDocxTests(unittest.TestCase):
    def test_safe_file_stem(self):
        self.assertEqual(safe_file_stem('Mi: guion/final? <v2>'), 'Mi guionfinal v2')
        self.assertEqual(safe_file_stem('  ...  '), '')
        self.assertEqual(safe_file_stem('a' * 200), 'a' * 80)

    def test_title_roundtrip_in_file(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, 't.guion')
        write_project(path, {'title': 'La noche', 'content': 'x'})
        self.assertEqual(read_project(path)['title'], 'La noche')
        write_project(path, {'title': 5, 'content': 'x'})
        self.assertEqual(read_project(path)['title'], '')

    def test_docx_structure_and_escaping(self):
        import io, zipfile
        from xml.dom import minidom
        data = build_docx('T & <t>', [('Sinopsis', 'a\n\nb\x00c\td')], subtitle='Sub')
        z = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual(z.namelist()[0], '[Content_Types].xml')
        self.assertFalse([n for n in z.namelist() if n.endswith('/')])   # sin entradas de carpeta
        for n in z.namelist():
            minidom.parseString(z.read(n))
        doc = z.read('word/document.xml').decode()
        self.assertIn('T &amp; &lt;t&gt;', doc)
        self.assertNotIn('\x00', doc)
        self.assertIn('<w:tab/>', doc)
        self.assertEqual(doc.count('<w:p>'), doc.count('</w:p>'))

    def test_docx_blank_lines_do_not_create_empty_paragraphs(self):
        xml = build_document_xml('', '', [('H', 'uno\n\n\ndos')])
        self.assertEqual(xml.count('<w:t xml:space="preserve">'), 3)   # H, uno, dos


if __name__ == '__main__':
    unittest.main()
