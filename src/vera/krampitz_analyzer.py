"""
V.E.R.A. Krampitz Load Analyzer
================================
Layer 1 of the Triple-Layer Verification System

Implements the Krampitz Rules (R1-R9) from Wessel (1992) to determine
the existential loading characteristic (e or n) of NTP formulas.

Source: Wessel, H. (1992). 'Existenz, Ununterscheidbarkeit, Identität.'
        Wissenschaftliche Zeitschrift der Humboldt-Universität zu Berlin,
        Reihe Geistes- und Sozialwiss. 41, pp. 30-39

        K.-H. Krampitz Dissertation B (1990)

Author: V.E.R.A. Open Source Initiative
Version: 0.1.0 (Prototype)
Date: January 2026

Copyright (C) 2026 V.E.R.A. Open Source Initiative

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple, Union
from abc import ABC, abstractmethod
import json


# =============================================================================
# Type Definitions
# =============================================================================

class Characteristic(Enum):
    """Existential loading characteristic."""
    E = "e"  # Existentially loaded - presupposes existence of subjects
    N = "n"  # Not existentially loaded - no existence presupposition
    

class FormulaType(Enum):
    """Types of NTP formulas."""
    PREDICATE = auto()      # P(x), Swan(x), etc.
    NEGATION = auto()       # ~A (outer negation)
    CONJUNCTION = auto()    # A âˆ§ B
    DISJUNCTION = auto()    # A âˆ¨ B
    IMPLICATION = auto()    # A âŠƒ B
    BICONDITIONAL = auto()  # A â‰¡ B
    UNIVERSAL = auto()      # âˆ€xA
    EXISTENTIAL = auto()    # âˆƒxA
    INNER_NEGATION = auto() # Â¬A (inner/contrary negation)


@dataclass
class AnalysisResult:
    """Result of Krampitz analysis."""
    formula_id: str
    original_formula: str
    characteristic: Characteristic
    rule_chain: List[str]
    requires_existence_check: bool
    subformula_analysis: List[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "formula_id": self.formula_id,
            "original_formula": self.original_formula,
            "characteristic": self.characteristic.value,
            "rule_chain": self.rule_chain,
            "requires_existence_check": self.requires_existence_check,
            "subformula_analysis": self.subformula_analysis
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# =============================================================================
# Formula AST (Abstract Syntax Tree)
# =============================================================================

class Formula(ABC):
    """Abstract base class for NTP formulas."""
    
    @abstractmethod
    def formula_type(self) -> FormulaType:
        pass
    
    @abstractmethod
    def __str__(self) -> str:
        pass
    
    @abstractmethod
    def get_subjects(self) -> List[str]:
        """Extract all subject terms from the formula."""
        pass


@dataclass
class Predicate(Formula):
    """Elementary predicate: P(x), Swan(x), WhiteFeathers(y), etc."""
    name: str
    subjects: List[str]
    
    def formula_type(self) -> FormulaType:
        return FormulaType.PREDICATE
    
    def __str__(self) -> str:
        return f"{self.name}({', '.join(self.subjects)})"
    
    def get_subjects(self) -> List[str]:
        return self.subjects.copy()


@dataclass  
class Negation(Formula):
    """Outer negation: ~A"""
    operand: Formula
    
    def formula_type(self) -> FormulaType:
        return FormulaType.NEGATION
    
    def __str__(self) -> str:
        return f"~{self.operand}"
    
    def get_subjects(self) -> List[str]:
        return self.operand.get_subjects()


@dataclass
class InnerNegation(Formula):
    """Inner (contrary) negation: Â¬A"""
    operand: Formula
    
    def formula_type(self) -> FormulaType:
        return FormulaType.INNER_NEGATION
    
    def __str__(self) -> str:
        return f"Â¬{self.operand}"
    
    def get_subjects(self) -> List[str]:
        return self.operand.get_subjects()


@dataclass
class Conjunction(Formula):
    """Conjunction: A âˆ§ B"""
    left: Formula
    right: Formula
    
    def formula_type(self) -> FormulaType:
        return FormulaType.CONJUNCTION
    
    def __str__(self) -> str:
        return f"({self.left} âˆ§ {self.right})"
    
    def get_subjects(self) -> List[str]:
        return self.left.get_subjects() + self.right.get_subjects()


@dataclass
class Disjunction(Formula):
    """Disjunction: A âˆ¨ B"""
    left: Formula
    right: Formula
    
    def formula_type(self) -> FormulaType:
        return FormulaType.DISJUNCTION
    
    def __str__(self) -> str:
        return f"({self.left} âˆ¨ {self.right})"
    
    def get_subjects(self) -> List[str]:
        return self.left.get_subjects() + self.right.get_subjects()


@dataclass
class Implication(Formula):
    """Material implication: A âŠƒ B"""
    antecedent: Formula
    consequent: Formula
    
    def formula_type(self) -> FormulaType:
        return FormulaType.IMPLICATION
    
    def __str__(self) -> str:
        return f"({self.antecedent} âŠƒ {self.consequent})"
    
    def get_subjects(self) -> List[str]:
        return self.antecedent.get_subjects() + self.consequent.get_subjects()


@dataclass
class Biconditional(Formula):
    """Biconditional: A â‰¡ B"""
    left: Formula
    right: Formula
    
    def formula_type(self) -> FormulaType:
        return FormulaType.BICONDITIONAL
    
    def __str__(self) -> str:
        return f"({self.left} â‰¡ {self.right})"
    
    def get_subjects(self) -> List[str]:
        return self.left.get_subjects() + self.right.get_subjects()


@dataclass
class Universal(Formula):
    """Universal quantifier: âˆ€xA"""
    variable: str
    body: Formula
    
    def formula_type(self) -> FormulaType:
        return FormulaType.UNIVERSAL
    
    def __str__(self) -> str:
        return f"âˆ€{self.variable}({self.body})"
    
    def get_subjects(self) -> List[str]:
        return self.body.get_subjects()


@dataclass
class Existential(Formula):
    """Existential quantifier: âˆƒxA"""
    variable: str
    body: Formula
    
    def formula_type(self) -> FormulaType:
        return FormulaType.EXISTENTIAL
    
    def __str__(self) -> str:
        return f"âˆƒ{self.variable}({self.body})"
    
    def get_subjects(self) -> List[str]:
        return self.body.get_subjects()


# =============================================================================
# Krampitz Load Analyzer - Core Engine
# =============================================================================

class KrampitzAnalyzer:
    """
    Implements the Krampitz Rules (R1-R9) for determining existential loading.
    
    Rules from Wessel (1992) / Krampitz (1990):
    
    R1. All elementary predicative statements are existentially loaded (e)
    R2. If A is e, then ~A is n
    R3. If A is n, then ~A is e
    R4. A âˆ¨ B is e âŸº (A is e AND B is e)
    R5. A âˆ§ B is e âŸº (A is e OR B is e)
    R6. A âŠƒ B is e âŸº (A is n AND B is e)
    R7. A â‰¡ B is n âŸº (both A and B are e) OR (both A and B are n)
    R8. âˆ€iA and âˆƒiA are e âŸº A is e
    R9. A definition A =Def B must be constructed such that A â‰¡ B is n
    """
    
    def __init__(self):
        self._formula_counter = 0
    
    def _generate_id(self) -> str:
        """Generate unique formula ID."""
        self._formula_counter += 1
        return f"KLA-{self._formula_counter:04d}"
    
    def analyze(self, formula: Formula) -> AnalysisResult:
        """
        Analyze a formula and determine its existential loading characteristic.
        
        Args:
            formula: The NTP formula to analyze
            
        Returns:
            AnalysisResult with characteristic, rule chain, and subformula analysis
        """
        rule_chain = []
        subformula_analysis = []
        
        characteristic = self._compute_characteristic(
            formula, rule_chain, subformula_analysis
        )
        
        return AnalysisResult(
            formula_id=self._generate_id(),
            original_formula=str(formula),
            characteristic=characteristic,
            rule_chain=rule_chain,
            requires_existence_check=(characteristic == Characteristic.E),
            subformula_analysis=subformula_analysis
        )
    
    def _compute_characteristic(
        self, 
        formula: Formula, 
        rule_chain: List[str],
        subformula_analysis: List[dict]
    ) -> Characteristic:
        """
        Recursively compute the existential loading characteristic.
        
        This implements MT1: Every formula has exactly one characteristic (e or n).
        """
        ftype = formula.formula_type()
        
        # R1: Elementary predicates are existentially loaded
        if ftype == FormulaType.PREDICATE:
            rule_chain.append("R1")
            subformula_analysis.append({
                "subformula": str(formula),
                "characteristic": "e",
                "rule": "R1"
            })
            return Characteristic.E
        
        # Inner negation: Â¬P is also existentially loaded (same as P)
        # From Wessel: Â¬P(sâ‚,...,sâ‚™) âŠ¢ E(sâ‚) âˆ§ ... âˆ§ E(sâ‚™)
        if ftype == FormulaType.INNER_NEGATION:
            inner = formula.operand
            char = self._compute_characteristic(inner, rule_chain, subformula_analysis)
            # Inner negation preserves existential loading
            rule_chain.append("R1-inner")
            subformula_analysis.append({
                "subformula": str(formula),
                "characteristic": char.value,
                "rule": "R1-inner"
            })
            return char
        
        # R2/R3: Outer negation flips characteristic
        if ftype == FormulaType.NEGATION:
            operand_char = self._compute_characteristic(
                formula.operand, rule_chain, subformula_analysis
            )
            if operand_char == Characteristic.E:
                rule_chain.append("R2")
                result = Characteristic.N
            else:
                rule_chain.append("R3")
                result = Characteristic.E
            subformula_analysis.append({
                "subformula": str(formula),
                "characteristic": result.value,
                "rule": rule_chain[-1]
            })
            return result
        
        # R4: Disjunction - e iff both are e
        if ftype == FormulaType.DISJUNCTION:
            left_char = self._compute_characteristic(
                formula.left, rule_chain, subformula_analysis
            )
            right_char = self._compute_characteristic(
                formula.right, rule_chain, subformula_analysis
            )
            rule_chain.append("R4")
            both_e = (left_char == Characteristic.E and right_char == Characteristic.E)
            result = Characteristic.E if both_e else Characteristic.N
            subformula_analysis.append({
                "subformula": str(formula),
                "characteristic": result.value,
                "rule": "R4",
                "detail": f"left={left_char.value}, right={right_char.value}"
            })
            return result
        
        # R5: Conjunction - e iff either is e
        if ftype == FormulaType.CONJUNCTION:
            left_char = self._compute_characteristic(
                formula.left, rule_chain, subformula_analysis
            )
            right_char = self._compute_characteristic(
                formula.right, rule_chain, subformula_analysis
            )
            rule_chain.append("R5")
            either_e = (left_char == Characteristic.E or right_char == Characteristic.E)
            result = Characteristic.E if either_e else Characteristic.N
            subformula_analysis.append({
                "subformula": str(formula),
                "characteristic": result.value,
                "rule": "R5",
                "detail": f"left={left_char.value}, right={right_char.value}"
            })
            return result
        
        # R6: Implication - e iff (antecedent is n AND consequent is e)
        if ftype == FormulaType.IMPLICATION:
            ant_char = self._compute_characteristic(
                formula.antecedent, rule_chain, subformula_analysis
            )
            cons_char = self._compute_characteristic(
                formula.consequent, rule_chain, subformula_analysis
            )
            rule_chain.append("R6")
            is_e = (ant_char == Characteristic.N and cons_char == Characteristic.E)
            result = Characteristic.E if is_e else Characteristic.N
            subformula_analysis.append({
                "subformula": str(formula),
                "characteristic": result.value,
                "rule": "R6",
                "detail": f"antecedent={ant_char.value}, consequent={cons_char.value}"
            })
            return result
        
        # R7: Biconditional - n iff (both e) or (both n)
        if ftype == FormulaType.BICONDITIONAL:
            left_char = self._compute_characteristic(
                formula.left, rule_chain, subformula_analysis
            )
            right_char = self._compute_characteristic(
                formula.right, rule_chain, subformula_analysis
            )
            rule_chain.append("R7")
            same_char = (left_char == right_char)
            result = Characteristic.N if same_char else Characteristic.E
            subformula_analysis.append({
                "subformula": str(formula),
                "characteristic": result.value,
                "rule": "R7",
                "detail": f"left={left_char.value}, right={right_char.value}"
            })
            return result
        
        # R8: Universal/Existential quantifiers - same as body
        if ftype in (FormulaType.UNIVERSAL, FormulaType.EXISTENTIAL):
            body_char = self._compute_characteristic(
                formula.body, rule_chain, subformula_analysis
            )
            rule_chain.append("R8")
            subformula_analysis.append({
                "subformula": str(formula),
                "characteristic": body_char.value,
                "rule": "R8"
            })
            return body_char
        
        raise ValueError(f"Unknown formula type: {ftype}")
    
    def validate_definition(self, definiendum: Formula, definiens: Formula) -> Tuple[bool, str]:
        """
        R9: Validate that a definition satisfies the requirement that A â‰¡ B is n.
        
        A definition A =Def B must be constructed such that A â‰¡ B is not
        existentially loaded.
        
        Args:
            definiendum: The term being defined (A)
            definiens: The defining expression (B)
            
        Returns:
            Tuple of (is_valid, explanation)
        """
        biconditional = Biconditional(definiendum, definiens)
        result = self.analyze(biconditional)
        
        if result.characteristic == Characteristic.N:
            return (True, f"Definition is valid: {biconditional} has characteristic n")
        else:
            return (False, f"Definition violates R9: {biconditional} has characteristic e (should be n)")


# =============================================================================
# Test Suite - Validated against VERA_Test_Strategy_v1.0
# =============================================================================

def run_test_suite():
    """
    Run the complete test suite from VERA_Test_Strategy_v1.0.
    
    Test cases are from the validated NTP source materials.
    """
    analyzer = KrampitzAnalyzer()
    
    print("=" * 70)
    print("V.E.R.A. Krampitz Load Analyzer - Test Suite")
    print("Source: VERA_Test_Strategy_v1.0 / Wessel (1992)")
    print("=" * 70)
    print()
    
    test_cases = [
        # KLA-001: R1 - Elementary predicate
        {
            "id": "KLA-001",
            "rule": "R1",
            "formula": Predicate("Swan", ["x"]),
            "expected": Characteristic.E,
            "description": "Elementary predicate Swan(x)"
        },
        # KLA-002: R2 - Negation of e gives n
        {
            "id": "KLA-002", 
            "rule": "R2",
            "formula": Negation(Predicate("Swan", ["x"])),
            "expected": Characteristic.N,
            "description": "~Swan(x) where Swan(x) is e"
        },
        # KLA-003: R3 - Negation of n gives e (double negation)
        {
            "id": "KLA-003",
            "rule": "R3",
            "formula": Negation(Negation(Predicate("Swan", ["x"]))),
            "expected": Characteristic.E,
            "description": "~~Swan(x) - double negation returns to e"
        },
        # KLA-004: R4 - Disjunction both e â†’ e
        {
            "id": "KLA-004",
            "rule": "R4",
            "formula": Disjunction(
                Predicate("P", ["x"]),
                Predicate("Q", ["x"])
            ),
            "expected": Characteristic.E,
            "description": "P(x) âˆ¨ Q(x) - both e â†’ e"
        },
        # KLA-005: R4 - Disjunction one n â†’ n
        {
            "id": "KLA-005",
            "rule": "R4",
            "formula": Disjunction(
                Predicate("P", ["x"]),
                Negation(Predicate("Q", ["x"]))
            ),
            "expected": Characteristic.N,
            "description": "P(x) âˆ¨ ~Q(x) - one n â†’ n"
        },
        # KLA-006: R5 - Conjunction either e â†’ e
        {
            "id": "KLA-006",
            "rule": "R5",
            "formula": Conjunction(
                Predicate("P", ["x"]),
                Negation(Predicate("Q", ["x"]))
            ),
            "expected": Characteristic.E,
            "description": "P(x) âˆ§ ~Q(x) - either e â†’ e"
        },
        # KLA-007: R6 - Implication (n âŠƒ e) â†’ e
        {
            "id": "KLA-007",
            "rule": "R6",
            "formula": Implication(
                Negation(Predicate("P", ["x"])),
                Predicate("Q", ["x"])
            ),
            "expected": Characteristic.E,
            "description": "~P(x) âŠƒ Q(x) - (n âŠƒ e) â†’ e"
        },
        # KLA-008: R7 - Biconditional same char â†’ n
        {
            "id": "KLA-008",
            "rule": "R7",
            "formula": Biconditional(
                Predicate("P", ["x"]),
                Predicate("Q", ["x"])
            ),
            "expected": Characteristic.N,
            "description": "P(x) â‰¡ Q(x) - both e â†’ n"
        },
        # KLA-009: R8 - Universal quantifier
        {
            "id": "KLA-009",
            "rule": "R8",
            "formula": Universal("x", Predicate("P", ["x"])),
            "expected": Characteristic.E,
            "description": "âˆ€x P(x) - same as body"
        },
        # Additional test: R6 - Implication (e âŠƒ e) â†’ n
        {
            "id": "KLA-010",
            "rule": "R6",
            "formula": Implication(
                Predicate("P", ["x"]),
                Predicate("Q", ["x"])
            ),
            "expected": Characteristic.N,
            "description": "P(x) âŠƒ Q(x) - (e âŠƒ e) â†’ n"
        },
        # Additional test: R7 - Biconditional different char â†’ e
        {
            "id": "KLA-011",
            "rule": "R7",
            "formula": Biconditional(
                Predicate("P", ["x"]),
                Negation(Predicate("Q", ["x"]))
            ),
            "expected": Characteristic.E,
            "description": "P(x) â‰¡ ~Q(x) - e and n â†’ e"
        },
        # Complex formula test
        {
            "id": "KLA-012",
            "rule": "Complex",
            "formula": Conjunction(
                Disjunction(
                    Predicate("Swan", ["x"]),
                    Predicate("Bird", ["x"])
                ),
                Negation(Predicate("Flies", ["x"]))
            ),
            "expected": Characteristic.E,
            "description": "(Swan(x) âˆ¨ Bird(x)) âˆ§ ~Flies(x) - complex"
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        result = analyzer.analyze(test["formula"])
        status = "âœ“ PASS" if result.characteristic == test["expected"] else "âœ— FAIL"
        
        if result.characteristic == test["expected"]:
            passed += 1
        else:
            failed += 1
        
        print(f"[{test['id']}] {status}")
        print(f"  Rule: {test['rule']}")
        print(f"  Formula: {test['formula']}")
        print(f"  Expected: {test['expected'].value}, Got: {result.characteristic.value}")
        print(f"  Rule Chain: {' â†’ '.join(result.rule_chain)}")
        print(f"  Requires E! Check: {result.requires_existence_check}")
        print()
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 70)
    
    # Test R9 - Definition validation
    print()
    print("R9 Definition Validation Test:")
    print("-" * 40)
    
    # Valid definition: Both sides have same characteristic
    valid_def = (
        Predicate("Bachelor", ["x"]),
        Conjunction(
            Predicate("Male", ["x"]),
            Predicate("Unmarried", ["x"])
        )
    )
    is_valid, explanation = analyzer.validate_definition(*valid_def)
    print(f"Bachelor(x) =Def Male(x) âˆ§ Unmarried(x)")
    print(f"  Result: {'âœ“ Valid' if is_valid else 'âœ— Invalid'}")
    print(f"  {explanation}")
    
    return passed, failed


# =============================================================================
# API Interface (for integration with V.E.R.A. services)
# =============================================================================

class KrampitzAPI:
    """
    REST-like API interface for the Krampitz Analyzer.
    Matches IF-003 specification from VERA_Interface_Specifications_v1.0
    """
    
    def __init__(self):
        self.analyzer = KrampitzAnalyzer()
    
    def analyze(self, formula: Formula) -> dict:
        """
        POST /api/v1/krampitz/analyze equivalent
        
        Returns response matching the interface specification.
        """
        result = self.analyzer.analyze(formula)
        return {
            "formula_id": result.formula_id,
            "original_formula": result.original_formula,
            "characteristic": result.characteristic.value,
            "rule_chain": result.rule_chain,
            "requires_existence_check": result.requires_existence_check,
            "subformula_analysis": result.subformula_analysis
        }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print()
    print("â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—")
    print("â•‘     V.E.R.A. - Verified Existence and Reason Architecture        â•‘")
    print("â•‘                  Krampitz Load Analyzer v0.1.0                    â•‘")
    print("â•‘                                                                    â•‘")
    print("â•‘  'Truth is a feature, not an option.'                             â•‘")
    print("â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•")
    print()
    
    # Run test suite
    passed, failed = run_test_suite()
    
    # Demo: Interactive analysis
    print()
    print("Demo: Analyzing a complex formula")
    print("-" * 40)
    
    analyzer = KrampitzAnalyzer()
    
    # "All swans have white feathers" - a classic NTP example
    # âˆ€x(Swan(x) âŠƒ WhiteFeathers(x))
    demo_formula = Universal(
        "x",
        Implication(
            Predicate("Swan", ["x"]),
            Predicate("WhiteFeathers", ["x"])
        )
    )
    
    result = analyzer.analyze(demo_formula)
    
    print(f"Formula: {demo_formula}")
    print(f"Characteristic: {result.characteristic.value}")
    print(f"Rule Chain: {' â†’ '.join(result.rule_chain)}")
    print(f"Requires E! Verification: {result.requires_existence_check}")
    print()
    print("Full Analysis (JSON):")
    print(result.to_json())
