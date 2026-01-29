"""
V.E.R.A. Formula Parser
========================
Converts natural language statements into NTP Formula AST

This module bridges natural language input to the Krampitz Load Analyzer,
enabling the V.E.R.A. pipeline to process user queries in plain English.

Architecture Role:
- Step 3 in Query Processing Pipeline (VERA_Process_Architecture_v1.0)
- Feeds into Layer 1: Krampitz Load Analyzer
- Extracts subjects for Layer 2: E! Verification Service

Author: V.E.R.A. Open Source Initiative
Version: 0.1.0 (Prototype)
Date: January 2026
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, Set
from enum import Enum, auto

# Import from Krampitz Analyzer
from krampitz_analyzer import (
    Formula, Predicate, Negation, InnerNegation,
    Conjunction, Disjunction, Implication, Biconditional,
    Universal, Existential, KrampitzAnalyzer, Characteristic
)


# =============================================================================
# Parse Result Types
# =============================================================================

class ParseStatus(Enum):
    """Status of parsing attempt."""
    SUCCESS = auto()
    PARTIAL = auto()  # Parsed but with uncertainty
    AMBIGUOUS = auto()  # Multiple interpretations possible
    FAILED = auto()


class StatementType(Enum):
    """Classification of natural language statement types."""
    UNIVERSAL_AFFIRMATIVE = auto()   # All X are Y
    UNIVERSAL_NEGATIVE = auto()       # No X are Y
    PARTICULAR_AFFIRMATIVE = auto()   # Some X are Y
    PARTICULAR_NEGATIVE = auto()      # Some X are not Y
    SINGULAR_AFFIRMATIVE = auto()     # X is Y
    SINGULAR_NEGATIVE = auto()        # X is not Y
    CONDITIONAL = auto()              # If X then Y
    CONJUNCTION = auto()              # X and Y
    DISJUNCTION = auto()              # X or Y
    EXISTENCE_CLAIM = auto()          # X exists / There is X
    IDENTITY = auto()                 # X is Y (identity)
    PROPERTY_QUERY = auto()           # What is the X of Y?
    UNKNOWN = auto()


@dataclass
class ParseResult:
    """Result of parsing a natural language statement."""
    status: ParseStatus
    formula: Optional[Formula]
    statement_type: StatementType
    original_text: str
    subjects: List[str]
    predicates: List[str]
    confidence: float  # 0.0 to 1.0
    warnings: List[str] = field(default_factory=list)
    alternatives: List['ParseResult'] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.name,
            "formula": str(self.formula) if self.formula else None,
            "statement_type": self.statement_type.name,
            "original_text": self.original_text,
            "subjects": self.subjects,
            "predicates": self.predicates,
            "confidence": self.confidence,
            "warnings": self.warnings
        }


# =============================================================================
# Pattern Definitions
# =============================================================================

@dataclass
class PatternRule:
    """A pattern matching rule for natural language."""
    pattern: str  # Regex pattern
    statement_type: StatementType
    extractor: str  # Name of extraction method
    priority: int = 0  # Higher = checked first
    

# Pattern rules ordered by specificity (most specific first)
PATTERN_RULES = [
    # Existence claims
    PatternRule(
        r"^(?:does\s+)?(\w+(?:\s+\w+)*)\s+exist(?:s)?(?:\?)?$",
        StatementType.EXISTENCE_CLAIM,
        "extract_existence",
        priority=100
    ),
    PatternRule(
        r"^there\s+(?:is|are|exists?)\s+(?:a\s+|an\s+|the\s+)?(\w+(?:\s+\w+)*)$",
        StatementType.EXISTENCE_CLAIM,
        "extract_existence",
        priority=100
    ),
    
    # Universal statements
    PatternRule(
        r"^all\s+(\w+(?:\s+\w+)*)\s+(?:are|have|is)\s+(\w+(?:\s+\w+)*)$",
        StatementType.UNIVERSAL_AFFIRMATIVE,
        "extract_universal_affirmative",
        priority=90
    ),
    PatternRule(
        r"^every\s+(\w+(?:\s+\w+)*)\s+(?:is|has|are)\s+(?:a\s+|an\s+)?(\w+(?:\s+\w+)*)$",
        StatementType.UNIVERSAL_AFFIRMATIVE,
        "extract_universal_affirmative",
        priority=90
    ),
    PatternRule(
        r"^no\s+(\w+(?:\s+\w+)*)\s+(?:are|is|have)\s+(\w+(?:\s+\w+)*)$",
        StatementType.UNIVERSAL_NEGATIVE,
        "extract_universal_negative",
        priority=90
    ),
    PatternRule(
        r"^(\w+(?:\s+\w+)*)\s+(?:are\s+)?never\s+(\w+(?:\s+\w+)*)$",
        StatementType.UNIVERSAL_NEGATIVE,
        "extract_universal_negative",
        priority=85
    ),
    
    # Particular statements - NEGATIVE must be checked BEFORE AFFIRMATIVE
    PatternRule(
        r"^some\s+(\w+(?:\s+\w+)*)\s+(?:are|is)\s+not\s+(\w+(?:\s+\w+)*)$",
        StatementType.PARTICULAR_NEGATIVE,
        "extract_particular_negative",
        priority=85  # Higher priority than affirmative
    ),
    PatternRule(
        r"^some\s+(\w+(?:\s+\w+)*)\s+(?:are|have|is)\s+(\w+(?:\s+\w+)*)$",
        StatementType.PARTICULAR_AFFIRMATIVE,
        "extract_particular_affirmative",
        priority=80
    ),
    PatternRule(
        r"^(?:there\s+(?:are|is)\s+)?some\s+(\w+(?:\s+\w+)*)\s+(?:that|which|who)\s+(?:are|is|have)\s+(\w+(?:\s+\w+)*)$",
        StatementType.PARTICULAR_AFFIRMATIVE,
        "extract_particular_affirmative",
        priority=80
    ),
    
    # Conditional statements
    PatternRule(
        r"^if\s+(.+?)\s*,?\s+then\s+(.+)$",
        StatementType.CONDITIONAL,
        "extract_conditional",
        priority=70
    ),
    PatternRule(
        r"^(.+?)\s+implies\s+(?:that\s+)?(.+)$",
        StatementType.CONDITIONAL,
        "extract_conditional",
        priority=70
    ),
    PatternRule(
        r"^whenever\s+(.+?)\s*,?\s+(.+)$",
        StatementType.CONDITIONAL,
        "extract_conditional",
        priority=70
    ),
    
    # Singular negative (must come before singular affirmative)
    PatternRule(
        r"^(?:the\s+)?(\w+(?:\s+\w+)*)\s+(?:is|are|has|does)\s+not\s+(?:a\s+|an\s+)?(\w+(?:\s+\w+)*)$",
        StatementType.SINGULAR_NEGATIVE,
        "extract_singular_negative",
        priority=65
    ),
    PatternRule(
        r"^(?:the\s+)?(\w+(?:\s+\w+)*)\s+(?:isn't|aren't|doesn't|don't|hasn't|haven't)\s+(?:a\s+|an\s+)?(\w+(?:\s+\w+)*)$",
        StatementType.SINGULAR_NEGATIVE,
        "extract_singular_negative",
        priority=65
    ),
    
    # Singular affirmative
    PatternRule(
        r"^(?:the\s+)?(\w+(?:\s+\w+)*)\s+(?:is|are|has)\s+(?:a\s+|an\s+)?(\w+(?:\s+\w+)*)$",
        StatementType.SINGULAR_AFFIRMATIVE,
        "extract_singular_affirmative",
        priority=60
    ),
    
    # Conjunction
    PatternRule(
        r"^(.+?)\s+and\s+(.+)$",
        StatementType.CONJUNCTION,
        "extract_conjunction",
        priority=40
    ),
    PatternRule(
        r"^both\s+(.+?)\s+and\s+(.+)$",
        StatementType.CONJUNCTION,
        "extract_conjunction",
        priority=45
    ),
    
    # Disjunction
    PatternRule(
        r"^(?:either\s+)?(.+?)\s+or\s+(.+)$",
        StatementType.DISJUNCTION,
        "extract_disjunction",
        priority=40
    ),
    
    # Property query
    PatternRule(
        r"^what\s+is\s+the\s+(\w+(?:\s+\w+)*)\s+of\s+(?:the\s+)?(\w+(?:\s+\w+)*)(?:\?)?$",
        StatementType.PROPERTY_QUERY,
        "extract_property_query",
        priority=50
    ),
]


# =============================================================================
# Formula Parser
# =============================================================================

class FormulaParser:
    """
    Parses natural language statements into NTP Formula AST.
    
    This parser uses pattern matching and heuristics to convert
    English statements into formal logical representations compatible
    with the Krampitz Load Analyzer.
    """
    
    def __init__(self):
        # Sort patterns by priority (descending)
        self.patterns = sorted(PATTERN_RULES, key=lambda p: -p.priority)
        self._var_counter = 0
    
    def _fresh_var(self) -> str:
        """Generate a fresh variable name."""
        self._var_counter += 1
        return f"x{self._var_counter}"
    
    def _reset_vars(self):
        """Reset variable counter for new parse."""
        self._var_counter = 0
    
    def _normalize(self, text: str) -> str:
        """Normalize input text for parsing."""
        # Lowercase
        text = text.lower().strip()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove trailing punctuation (except ?)
        text = re.sub(r'[.!]+$', '', text)
        return text
    
    def _to_predicate_name(self, phrase: str) -> str:
        """Convert a phrase to a predicate name (PascalCase)."""
        words = phrase.strip().split()
        return ''.join(word.capitalize() for word in words)
    
    def _to_subject_name(self, phrase: str) -> str:
        """Convert a phrase to a subject/constant name."""
        # Keep as-is but strip articles
        phrase = re.sub(r'^(a|an|the)\s+', '', phrase.strip())
        return phrase
    
    def parse(self, text: str) -> ParseResult:
        """
        Parse a natural language statement into an NTP formula.
        
        Args:
            text: Natural language statement
            
        Returns:
            ParseResult with formula (if successful) and metadata
        """
        self._reset_vars()
        original = text
        normalized = self._normalize(text)
        
        # Try each pattern
        for rule in self.patterns:
            match = re.match(rule.pattern, normalized, re.IGNORECASE)
            if match:
                extractor = getattr(self, rule.extractor, None)
                if extractor:
                    result = extractor(match, original, rule.statement_type)
                    if result.status in (ParseStatus.SUCCESS, ParseStatus.PARTIAL):
                        return result
        
        # No pattern matched - try fallback parsing
        return self._fallback_parse(normalized, original)
    
    # =========================================================================
    # Extraction Methods
    # =========================================================================
    
    def extract_existence(self, match: re.Match, original: str, 
                         stmt_type: StatementType) -> ParseResult:
        """Extract existence claim: 'X exists', 'Does X exist?'"""
        subject = self._to_subject_name(match.group(1))
        
        # E!(subject) - existence predicate
        formula = Predicate("E!", [subject])
        
        return ParseResult(
            status=ParseStatus.SUCCESS,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=[subject],
            predicates=["E!"],
            confidence=0.95
        )
    
    def extract_universal_affirmative(self, match: re.Match, original: str,
                                       stmt_type: StatementType) -> ParseResult:
        """Extract: 'All X are Y' → ∀x(X(x) ⊃ Y(x))"""
        subject_class = self._to_predicate_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        var = self._fresh_var()
        
        # ∀x(SubjectClass(x) ⊃ Predicate(x))
        formula = Universal(
            var,
            Implication(
                Predicate(subject_class, [var]),
                Predicate(predicate, [var])
            )
        )
        
        return ParseResult(
            status=ParseStatus.SUCCESS,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=[subject_class],  # Class name, not individual
            predicates=[subject_class, predicate],
            confidence=0.9
        )
    
    def extract_universal_negative(self, match: re.Match, original: str,
                                   stmt_type: StatementType) -> ParseResult:
        """Extract: 'No X are Y' → ∀x(X(x) ⊃ ~Y(x))"""
        subject_class = self._to_predicate_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        var = self._fresh_var()
        
        # ∀x(SubjectClass(x) ⊃ ~Predicate(x))
        formula = Universal(
            var,
            Implication(
                Predicate(subject_class, [var]),
                Negation(Predicate(predicate, [var]))
            )
        )
        
        return ParseResult(
            status=ParseStatus.SUCCESS,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=[subject_class],
            predicates=[subject_class, predicate],
            confidence=0.9
        )
    
    def extract_particular_affirmative(self, match: re.Match, original: str,
                                        stmt_type: StatementType) -> ParseResult:
        """Extract: 'Some X are Y' → ∃x(X(x) ∧ Y(x))"""
        subject_class = self._to_predicate_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        var = self._fresh_var()
        
        # ∃x(SubjectClass(x) ∧ Predicate(x))
        formula = Existential(
            var,
            Conjunction(
                Predicate(subject_class, [var]),
                Predicate(predicate, [var])
            )
        )
        
        return ParseResult(
            status=ParseStatus.SUCCESS,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=[subject_class],
            predicates=[subject_class, predicate],
            confidence=0.9
        )
    
    def extract_particular_negative(self, match: re.Match, original: str,
                                    stmt_type: StatementType) -> ParseResult:
        """Extract: 'Some X are not Y' → ∃x(X(x) ∧ ~Y(x))"""
        subject_class = self._to_predicate_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        var = self._fresh_var()
        
        # ∃x(SubjectClass(x) ∧ ~Predicate(x))
        formula = Existential(
            var,
            Conjunction(
                Predicate(subject_class, [var]),
                Negation(Predicate(predicate, [var]))
            )
        )
        
        return ParseResult(
            status=ParseStatus.SUCCESS,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=[subject_class],
            predicates=[subject_class, predicate],
            confidence=0.9
        )
    
    def extract_singular_affirmative(self, match: re.Match, original: str,
                                      stmt_type: StatementType) -> ParseResult:
        """Extract: 'X is Y' → Y(x) where x is the subject"""
        subject = self._to_subject_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        
        # Predicate(subject)
        formula = Predicate(predicate, [subject])
        
        return ParseResult(
            status=ParseStatus.SUCCESS,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=[subject],
            predicates=[predicate],
            confidence=0.85
        )
    
    def extract_singular_negative(self, match: re.Match, original: str,
                                   stmt_type: StatementType) -> ParseResult:
        """Extract: 'X is not Y' → ~Y(x)"""
        subject = self._to_subject_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        
        # ~Predicate(subject)
        formula = Negation(Predicate(predicate, [subject]))
        
        return ParseResult(
            status=ParseStatus.SUCCESS,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=[subject],
            predicates=[predicate],
            confidence=0.85
        )
    
    def extract_conditional(self, match: re.Match, original: str,
                            stmt_type: StatementType) -> ParseResult:
        """Extract: 'If P then Q' → P ⊃ Q (recursively parsed)"""
        antecedent_text = match.group(1).strip()
        consequent_text = match.group(2).strip()
        
        # Recursively parse sub-statements
        ant_result = self.parse(antecedent_text)
        cons_result = self.parse(consequent_text)
        
        warnings = []
        
        if ant_result.status == ParseStatus.FAILED:
            # Fall back to simple predicate
            ant_formula = Predicate(self._to_predicate_name(antecedent_text), [self._fresh_var()])
            warnings.append(f"Could not parse antecedent '{antecedent_text}', using simple predicate")
        else:
            ant_formula = ant_result.formula
            warnings.extend(ant_result.warnings)
        
        if cons_result.status == ParseStatus.FAILED:
            cons_formula = Predicate(self._to_predicate_name(consequent_text), [self._fresh_var()])
            warnings.append(f"Could not parse consequent '{consequent_text}', using simple predicate")
        else:
            cons_formula = cons_result.formula
            warnings.extend(cons_result.warnings)
        
        formula = Implication(ant_formula, cons_formula)
        
        # Collect all subjects
        subjects = list(set(ant_result.subjects + cons_result.subjects))
        predicates = list(set(ant_result.predicates + cons_result.predicates))
        
        confidence = min(ant_result.confidence, cons_result.confidence) * 0.9
        
        return ParseResult(
            status=ParseStatus.SUCCESS if not warnings else ParseStatus.PARTIAL,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=subjects,
            predicates=predicates,
            confidence=confidence,
            warnings=warnings
        )
    
    def extract_conjunction(self, match: re.Match, original: str,
                            stmt_type: StatementType) -> ParseResult:
        """Extract: 'P and Q' → P ∧ Q"""
        left_text = match.group(1).strip()
        right_text = match.group(2).strip()
        
        left_result = self.parse(left_text)
        right_result = self.parse(right_text)
        
        warnings = []
        
        if left_result.status == ParseStatus.FAILED:
            left_formula = Predicate(self._to_predicate_name(left_text), [self._fresh_var()])
            warnings.append(f"Could not parse left conjunct '{left_text}'")
        else:
            left_formula = left_result.formula
            warnings.extend(left_result.warnings)
        
        if right_result.status == ParseStatus.FAILED:
            right_formula = Predicate(self._to_predicate_name(right_text), [self._fresh_var()])
            warnings.append(f"Could not parse right conjunct '{right_text}'")
        else:
            right_formula = right_result.formula
            warnings.extend(right_result.warnings)
        
        formula = Conjunction(left_formula, right_formula)
        
        subjects = list(set(left_result.subjects + right_result.subjects))
        predicates = list(set(left_result.predicates + right_result.predicates))
        
        return ParseResult(
            status=ParseStatus.SUCCESS if not warnings else ParseStatus.PARTIAL,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=subjects,
            predicates=predicates,
            confidence=min(left_result.confidence, right_result.confidence) * 0.85,
            warnings=warnings
        )
    
    def extract_disjunction(self, match: re.Match, original: str,
                            stmt_type: StatementType) -> ParseResult:
        """Extract: 'P or Q' → P ∨ Q"""
        left_text = match.group(1).strip()
        right_text = match.group(2).strip()
        
        left_result = self.parse(left_text)
        right_result = self.parse(right_text)
        
        warnings = []
        
        if left_result.status == ParseStatus.FAILED:
            left_formula = Predicate(self._to_predicate_name(left_text), [self._fresh_var()])
            warnings.append(f"Could not parse left disjunct '{left_text}'")
        else:
            left_formula = left_result.formula
        
        if right_result.status == ParseStatus.FAILED:
            right_formula = Predicate(self._to_predicate_name(right_text), [self._fresh_var()])
            warnings.append(f"Could not parse right disjunct '{right_text}'")
        else:
            right_formula = right_result.formula
        
        formula = Disjunction(left_formula, right_formula)
        
        subjects = list(set(left_result.subjects + right_result.subjects))
        predicates = list(set(left_result.predicates + right_result.predicates))
        
        return ParseResult(
            status=ParseStatus.SUCCESS if not warnings else ParseStatus.PARTIAL,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=subjects,
            predicates=predicates,
            confidence=min(left_result.confidence, right_result.confidence) * 0.85,
            warnings=warnings
        )
    
    def extract_property_query(self, match: re.Match, original: str,
                               stmt_type: StatementType) -> ParseResult:
        """Extract: 'What is the X of Y?' → Query for X(Y)"""
        property_name = self._to_predicate_name(match.group(1))
        subject = self._to_subject_name(match.group(2))
        
        # Represent as a predicate (the actual query handling is downstream)
        formula = Predicate(property_name, [subject])
        
        return ParseResult(
            status=ParseStatus.SUCCESS,
            formula=formula,
            statement_type=stmt_type,
            original_text=original,
            subjects=[subject],
            predicates=[property_name],
            confidence=0.8,
            warnings=["This is a query, not an assertion"]
        )
    
    def _fallback_parse(self, normalized: str, original: str) -> ParseResult:
        """Fallback parsing when no pattern matches."""
        # Try to extract any noun phrases as subjects
        # and treat the whole thing as a predicate
        
        words = normalized.split()
        
        if len(words) >= 2:
            # Guess: first word(s) are subject, rest is predicate
            # This is very approximate
            subject = words[0]
            predicate = '_'.join(words[1:])
            
            formula = Predicate(self._to_predicate_name(predicate), [subject])
            
            return ParseResult(
                status=ParseStatus.PARTIAL,
                formula=formula,
                statement_type=StatementType.UNKNOWN,
                original_text=original,
                subjects=[subject],
                predicates=[predicate],
                confidence=0.3,
                warnings=["No pattern matched; using fallback parsing"]
            )
        
        return ParseResult(
            status=ParseStatus.FAILED,
            formula=None,
            statement_type=StatementType.UNKNOWN,
            original_text=original,
            subjects=[],
            predicates=[],
            confidence=0.0,
            warnings=["Could not parse statement"]
        )


# =============================================================================
# Integrated Pipeline: Parser + Analyzer
# =============================================================================

class NTPPipeline:
    """
    Integrated pipeline combining Formula Parser and Krampitz Analyzer.
    
    This represents the first two steps of the V.E.R.A. verification:
    1. Parse natural language → NTP Formula
    2. Analyze formula → Existential loading characteristic
    """
    
    def __init__(self):
        self.parser = FormulaParser()
        self.analyzer = KrampitzAnalyzer()
    
    def process(self, text: str) -> Dict[str, Any]:
        """
        Process a natural language statement through the NTP pipeline.
        
        Args:
            text: Natural language input
            
        Returns:
            Complete analysis including parse result and Krampitz analysis
        """
        # Step 1: Parse
        parse_result = self.parser.parse(text)
        
        result = {
            "input": text,
            "parse": parse_result.to_dict(),
        }
        
        # Step 2: Analyze (if parsing succeeded)
        if parse_result.formula:
            krampitz_result = self.analyzer.analyze(parse_result.formula)
            result["analysis"] = krampitz_result.to_dict()
            result["requires_existence_check"] = krampitz_result.requires_existence_check
            result["subjects_to_verify"] = parse_result.subjects if krampitz_result.requires_existence_check else []
        else:
            result["analysis"] = None
            result["requires_existence_check"] = False
            result["subjects_to_verify"] = []
        
        return result


# =============================================================================
# Test Suite
# =============================================================================

def run_parser_tests():
    """Run comprehensive parser test suite."""
    parser = FormulaParser()
    analyzer = KrampitzAnalyzer()
    
    print("=" * 70)
    print("V.E.R.A. Formula Parser - Test Suite")
    print("=" * 70)
    print()
    
    test_cases = [
        # Universal statements
        ("All swans are white", StatementType.UNIVERSAL_AFFIRMATIVE, Characteristic.N),
        ("All men are mortal", StatementType.UNIVERSAL_AFFIRMATIVE, Characteristic.N),
        ("Every bird has feathers", StatementType.UNIVERSAL_AFFIRMATIVE, Characteristic.N),
        ("No fish are mammals", StatementType.UNIVERSAL_NEGATIVE, Characteristic.N),
        
        # Particular statements  
        ("Some birds are black", StatementType.PARTICULAR_AFFIRMATIVE, Characteristic.E),
        ("Some swans are not white", StatementType.PARTICULAR_NEGATIVE, Characteristic.E),
        
        # Singular statements
        ("Socrates is mortal", StatementType.SINGULAR_AFFIRMATIVE, Characteristic.E),
        ("The moon is round", StatementType.SINGULAR_AFFIRMATIVE, Characteristic.E),
        ("Pegasus is not real", StatementType.SINGULAR_NEGATIVE, Characteristic.N),
        
        # Existence claims
        ("Does the Higgs boson exist?", StatementType.EXISTENCE_CLAIM, Characteristic.E),
        ("Unicorns exist", StatementType.EXISTENCE_CLAIM, Characteristic.E),
        ("There is a planet beyond Neptune", StatementType.EXISTENCE_CLAIM, Characteristic.E),
        
        # Conditionals
        ("If it rains then the ground is wet", StatementType.CONDITIONAL, None),  # Complex
        ("If Socrates is a man then Socrates is mortal", StatementType.CONDITIONAL, None),
        
        # Property queries
        ("What is the mass of the Higgs boson?", StatementType.PROPERTY_QUERY, Characteristic.E),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected_type, expected_char in test_cases:
        result = parser.parse(text)
        
        type_match = result.statement_type == expected_type
        
        char_match = True
        actual_char = None
        if result.formula and expected_char:
            analysis = analyzer.analyze(result.formula)
            actual_char = analysis.characteristic
            char_match = actual_char == expected_char
        
        success = type_match and char_match and result.status != ParseStatus.FAILED
        
        if success:
            passed += 1
            status = "✓ PASS"
        else:
            failed += 1
            status = "✗ FAIL"
        
        print(f"[{status}] \"{text}\"")
        print(f"  Type: {result.statement_type.name} (expected: {expected_type.name}) {'✓' if type_match else '✗'}")
        if result.formula:
            print(f"  Formula: {result.formula}")
            if actual_char:
                print(f"  Characteristic: {actual_char.value} (expected: {expected_char.value if expected_char else 'N/A'}) {'✓' if char_match else '✗'}")
        print(f"  Subjects: {result.subjects}")
        print(f"  Confidence: {result.confidence:.2f}")
        if result.warnings:
            print(f"  Warnings: {result.warnings}")
        print()
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 70)
    
    return passed, failed


def run_pipeline_demo():
    """Demonstrate the full NTP pipeline."""
    print()
    print("=" * 70)
    print("V.E.R.A. NTP Pipeline - Integration Demo")
    print("=" * 70)
    print()
    
    pipeline = NTPPipeline()
    
    demo_statements = [
        "All swans are white",
        "Socrates is mortal",
        "Does the Higgs boson exist?",
        "Some unicorns have golden horns",
        "If it is a mammal then it is warm-blooded",
    ]
    
    for statement in demo_statements:
        print(f"Input: \"{statement}\"")
        print("-" * 50)
        
        result = pipeline.process(statement)
        
        if result["parse"]["formula"]:
            print(f"Formula: {result['parse']['formula']}")
            print(f"Type: {result['parse']['statement_type']}")
            print(f"Characteristic: {result['analysis']['characteristic']}")
            print(f"Rule Chain: {' → '.join(result['analysis']['rule_chain'])}")
            print(f"Requires E! Check: {result['requires_existence_check']}")
            if result['subjects_to_verify']:
                print(f"Subjects to Verify: {result['subjects_to_verify']}")
        else:
            print(f"Parse failed: {result['parse']['warnings']}")
        
        print()


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     V.E.R.A. - Verified Existence and Reason Architecture        ║")
    print("║                    Formula Parser v0.1.0                          ║")
    print("║                                                                    ║")
    print("║  Converting natural language to NTP formulas                      ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    
    # Run tests
    passed, failed = run_parser_tests()
    
    # Run demo
    run_pipeline_demo()
    
    # Interactive mode hint
    print("=" * 70)
    print("Interactive Usage:")
    print("  from formula_parser import NTPPipeline")
    print("  pipeline = NTPPipeline()")
    print("  result = pipeline.process('All swans are white')")
    print("=" * 70)
