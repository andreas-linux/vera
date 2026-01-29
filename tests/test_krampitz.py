"""
Tests for Krampitz Load Analyzer (Layer 1)

Test cases based on VERA_Test_Strategy_v1.0 and validated
NTP rules from Wessel (1992).
"""

import pytest
from vera import (
    KrampitzAnalyzer,
    Characteristic,
    Predicate,
    Negation,
    Conjunction,
    Disjunction,
    Implication,
    Biconditional,
    Universal,
    Existential,
)


@pytest.fixture
def analyzer():
    """Create a fresh analyzer instance for each test."""
    return KrampitzAnalyzer()


class TestR1ElementaryPredicates:
    """R1: All elementary predicative statements are existentially loaded (e)."""
    
    def test_simple_predicate(self, analyzer):
        """KLA-001: Swan(x) should be e."""
        formula = Predicate("Swan", ["x"])
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.E
        assert "R1" in result.rule_chain
    
    def test_multi_argument_predicate(self, analyzer):
        """Predicate with multiple arguments."""
        formula = Predicate("Loves", ["romeo", "juliet"])
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.E


class TestR2R3Negation:
    """R2: If A is e, then ~A is n. R3: If A is n, then ~A is e."""
    
    def test_negation_of_e_is_n(self, analyzer):
        """KLA-002: ~Swan(x) should be n (R2)."""
        formula = Negation(Predicate("Swan", ["x"]))
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.N
        assert "R2" in result.rule_chain
    
    def test_double_negation(self, analyzer):
        """KLA-003: ~~Swan(x) should be e (R3 applied to R2 result)."""
        formula = Negation(Negation(Predicate("Swan", ["x"])))
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.E
        assert "R3" in result.rule_chain


class TestR4Disjunction:
    """R4: A ∨ B is e ⟺ (A is e AND B is e)."""
    
    def test_both_e_gives_e(self, analyzer):
        """KLA-004: Swan(x) ∨ Bird(x) should be e."""
        formula = Disjunction(
            Predicate("Swan", ["x"]),
            Predicate("Bird", ["x"])
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.E
        assert "R4" in result.rule_chain
    
    def test_one_n_gives_n(self, analyzer):
        """KLA-005: Swan(x) ∨ ~Bird(x) should be n."""
        formula = Disjunction(
            Predicate("Swan", ["x"]),
            Negation(Predicate("Bird", ["x"]))
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.N


class TestR5Conjunction:
    """R5: A ∧ B is e ⟺ (A is e OR B is e)."""
    
    def test_either_e_gives_e(self, analyzer):
        """KLA-006: Swan(x) ∧ ~Flies(x) should be e."""
        formula = Conjunction(
            Predicate("Swan", ["x"]),
            Negation(Predicate("Flies", ["x"]))
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.E
        assert "R5" in result.rule_chain
    
    def test_both_n_gives_n(self, analyzer):
        """~P ∧ ~Q should be n."""
        formula = Conjunction(
            Negation(Predicate("P", ["x"])),
            Negation(Predicate("Q", ["x"]))
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.N


class TestR6Implication:
    """R6: A ⊃ B is e ⟺ (A is n AND B is e)."""
    
    def test_n_implies_e_gives_e(self, analyzer):
        """KLA-007: ~P(x) ⊃ Q(x) should be e."""
        formula = Implication(
            Negation(Predicate("P", ["x"])),
            Predicate("Q", ["x"])
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.E
        assert "R6" in result.rule_chain
    
    def test_e_implies_e_gives_n(self, analyzer):
        """KLA-010: P(x) ⊃ Q(x) should be n."""
        formula = Implication(
            Predicate("P", ["x"]),
            Predicate("Q", ["x"])
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.N


class TestR7Biconditional:
    """R7: A ≡ B is n ⟺ (both A and B are e) OR (both A and B are n)."""
    
    def test_same_char_gives_n(self, analyzer):
        """KLA-008: P(x) ≡ Q(x) (both e) should be n."""
        formula = Biconditional(
            Predicate("P", ["x"]),
            Predicate("Q", ["x"])
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.N
        assert "R7" in result.rule_chain
    
    def test_different_char_gives_e(self, analyzer):
        """KLA-011: P(x) ≡ ~Q(x) should be e."""
        formula = Biconditional(
            Predicate("P", ["x"]),
            Negation(Predicate("Q", ["x"]))
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.E


class TestR8Quantifiers:
    """R8: ∀iA and ∃iA are e ⟺ A is e."""
    
    def test_universal_preserves_char(self, analyzer):
        """KLA-009: ∀x(Swan(x) ⊃ White(x)) should be n."""
        formula = Universal(
            "x",
            Implication(
                Predicate("Swan", ["x"]),
                Predicate("White", ["x"])
            )
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.N
        assert "R8" in result.rule_chain
    
    def test_existential_preserves_char(self, analyzer):
        """∃x(Swan(x) ∧ Black(x)) should be e."""
        formula = Existential(
            "x",
            Conjunction(
                Predicate("Swan", ["x"]),
                Predicate("Black", ["x"])
            )
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.E


class TestComplexFormulas:
    """Test complex nested formulas."""
    
    def test_complex_formula(self, analyzer):
        """KLA-012: (Swan(x) ∨ Bird(x)) ∧ ~Flies(x) should be e."""
        formula = Conjunction(
            Disjunction(
                Predicate("Swan", ["x"]),
                Predicate("Bird", ["x"])
            ),
            Negation(Predicate("Flies", ["x"]))
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.E
    
    def test_all_swans_white(self, analyzer):
        """Classic example: ∀x(Swan(x) ⊃ White(x)) is n-type."""
        formula = Universal(
            "x",
            Implication(
                Predicate("Swan", ["x"]),
                Predicate("White", ["x"])
            )
        )
        result = analyzer.analyze(formula)
        assert result.characteristic == Characteristic.N
        # This means: no existence presupposition!
        # Safe to say even if no swans exist (vacuously true)


class TestR9DefinitionValidation:
    """R9: Definition A =Def B requires A ≡ B to be n."""
    
    def test_valid_definition(self, analyzer):
        """Bachelor =Def Male ∧ Unmarried should be valid."""
        definiendum = Predicate("Bachelor", ["x"])
        definiens = Conjunction(
            Predicate("Male", ["x"]),
            Predicate("Unmarried", ["x"])
        )
        
        is_valid, message = analyzer.validate_definition(definiendum, definiens)
        assert is_valid
        assert "valid" in message.lower()
    
    def test_invalid_definition(self, analyzer):
        """Definition with e-type biconditional should be invalid."""
        definiendum = Predicate("P", ["x"])
        definiens = Negation(Predicate("Q", ["x"]))  # e ≡ n = e, invalid
        
        is_valid, message = analyzer.validate_definition(definiendum, definiens)
        assert not is_valid


class TestRequiresExistenceCheck:
    """Test that requires_existence_check is set correctly."""
    
    def test_e_type_requires_check(self, analyzer):
        """e-type formulas require existence verification."""
        formula = Predicate("Mortal", ["socrates"])
        result = analyzer.analyze(formula)
        assert result.requires_existence_check is True
    
    def test_n_type_no_check(self, analyzer):
        """n-type formulas don't require existence verification."""
        formula = Universal(
            "x",
            Implication(
                Predicate("Man", ["x"]),
                Predicate("Mortal", ["x"])
            )
        )
        result = analyzer.analyze(formula)
        assert result.requires_existence_check is False
