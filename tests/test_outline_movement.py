import unittest

from src.parser import extract_outline, move_outline_block, normalize_structural_case, classify


class OutlineMovementTests(unittest.TestCase):
    def setUp(self):
        self.text = (
            "# ACTO 1\nTexto de apertura del acto 1\n"
            "## SECUENCIA 1\nTexto de secuencia 1\n"
            "INT. CASA - DÍA\nAcción de casa\nPERSONAJE\nDiálogo de casa\n"
            "INT. CALLE - NOCHE\nAcción de calle\n"
            "## SECUENCIA 2\nTexto de secuencia 2\n"
            "EXT. PARQUE - DÍA\nAcción de parque\n"
            "# ACTO 2\nTexto de apertura del acto 2\n"
            "INT. FINAL - NOCHE\nAcción final\n"
        )
        self.outline = extract_outline(self.text)

    def test_scene_moves_with_its_entire_content(self):
        moved = move_outline_block(self.text, self.outline, 2, 1)
        self.assertLess(moved.index("INT. CALLE"), moved.index("INT. CASA"))
        self.assertLess(moved.index("Acción de calle"), moved.index("INT. CASA"))
        self.assertLess(moved.index("INT. CASA"), moved.index("Diálogo de casa"))
        self.assertLess(moved.index("Diálogo de casa"), moved.index("## SECUENCIA 2"))

    def test_sequence_moves_with_all_its_scenes(self):
        moved = move_outline_block(self.text, self.outline, 1, 1)
        self.assertLess(moved.index("## SECUENCIA 2"), moved.index("## SECUENCIA 1"))
        self.assertLess(moved.index("Acción de parque"), moved.index("## SECUENCIA 1"))
        self.assertLess(moved.index("## SECUENCIA 1"), moved.index("Acción de casa"))
        self.assertLess(moved.index("# ACTO 1"), moved.index("Acción de casa"))

    def test_act_moves_with_all_its_sequences_and_scenes(self):
        moved = move_outline_block(self.text, self.outline, 0, 1)
        self.assertLess(moved.index("# ACTO 2"), moved.index("# ACTO 1"))
        self.assertLess(moved.index("Acción final"), moved.index("# ACTO 1"))
        self.assertLess(moved.index("# ACTO 1"), moved.index("Acción de casa"))

    def test_scene_cannot_cross_sequence_boundary(self):
        # La segunda escena de la secuencia 1 no puede saltar a la secuencia 2.
        self.assertIsNone(move_outline_block(self.text, self.outline, 3, 1))


    def test_structural_headings_are_normalized_to_uppercase(self):
        source = "# acto 1\n\n## secuencia 2\n\nint. casa - día\n\nMaría\nHola.\n"
        normalized = normalize_structural_case(source)
        self.assertIn("# ACTO 1", normalized)
        self.assertIn("## SECUENCIA 2", normalized)
        self.assertIn("INT. CASA - DÍA", normalized)
        self.assertIn("MARÍA\nHola.", normalized)

    def test_character_cue_at_document_start_is_uppercase(self):
        normalized = normalize_structural_case("María\nHola.")
        self.assertEqual(normalized, "MARÍA\nHola.")

    def test_action_and_dialogue_keep_normal_sentence_case(self):
        source = "# acto 1\n\nMaría entra en la habitación.\n\nMaría\nBuenos días.\n"
        normalized = normalize_structural_case(source)
        self.assertIn("María entra en la habitación.", normalized)
        self.assertIn("MARÍA\nBuenos días.", normalized)

    def test_first_or_last_sibling_boundary_is_safe(self):
        self.assertIsNone(move_outline_block(self.text, self.outline, 0, -1))
        self.assertIsNone(move_outline_block(self.text, self.outline, 6, 1))


if __name__ == "__main__":
    unittest.main()
