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
    # Capitalised entity candidates present in the text but NOT extracted
    # as subjects. Surfaced so the pipeline can flag what was not verified
    # (defect P1-C). Full multi-entity claim extraction remains the
    # CONTRIBUTING-flagged research problem.
    entity_candidates: List[str] = field(default_factory=list)
    # Subjects that are descriptive noun phrases (definite descriptions),
    # not entity constants. The pipeline uses this to state the real
    # refusal reason instead of presenting a plain corpus miss (P1-D).
    descriptive_subjects: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.name,
            "formula": str(self.formula) if self.formula else None,
            "statement_type": self.statement_type.name,
            "original_text": self.original_text,
            "subjects": self.subjects,
            "predicates": self.predicates,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "entity_candidates": self.entity_candidates,
            "descriptive_subjects": self.descriptive_subjects
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
    
    # Punctuation stripped from the ends of extracted subject tokens.
    # Internal hyphens and apostrophes are preserved (anti-inflammatory,
    # O'Brien).
    _TOKEN_EDGE_PUNCT = ".,;:!?\"'()[]{}"

    # Words that begin a capitalised run for orthographic reasons only
    # (sentence-initial position, quantifiers, articles). Used by the
    # entity candidate detector.
    _CANDIDATE_STOPWORDS = {
        "the", "a", "an", "if", "all", "no", "some", "every", "there",
        "what", "does", "do", "is", "are", "both", "either", "whenever",
        "it", "this", "that", "these", "those", "i", "not", "then",
    }

    def _clean_subject_token(self, token: str) -> str:
        """
        Normalise an extracted subject token (defect P1-A).

        Strips leading and trailing punctuation and collapses internal
        whitespace. Without this, fallback extraction captured tokens
        such as 'aspirin,' (with the comma), which then missed real
        E! Corpus entries and produced false refusals of verified
        entities.
        """
        token = token.strip().strip(self._TOKEN_EDGE_PUNCT)
        token = re.sub(r'\s+', ' ', token)
        return token.strip()

    def _to_subject_name(self, phrase: str) -> str:
        """Convert a phrase to a subject/constant name."""
        # Strip articles, then normalise the token edges (P1-A).
        phrase = re.sub(r'^(a|an|the)\s+', '', phrase.strip())
        return self._clean_subject_token(phrase)
    
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
        result = self._match_patterns(normalized, original)
        
        # No pattern matched: try reducing one inserted subordinate
        # clause to expose the main clause (defect P1-B). Applied only
        # when the full sentence matched no pattern, so constructions
        # that already parse are never touched.
        if result is None:
            reduction = self._reduce_parenthetical(normalized)
            if reduction:
                reduced_text, removed_clause = reduction
                reduced_result = self._match_patterns(reduced_text, original)
                if reduced_result is not None:
                    reduced_result.confidence = round(reduced_result.confidence * 0.9, 4)
                    reduced_result.warnings.append(
                        f"Subordinate clause '{removed_clause}' removed to parse the "
                        f"main clause; the clause content was NOT parsed or verified "
                        f"(multi-clause claim extraction is a v0.2 research problem)."
                    )
                    result = reduced_result
        
        # Still nothing: fall back to token guessing
        if result is None:
            result = self._fallback_parse(normalized, original)
        
        # Annotation choke point (defects P1-C and P1-D): every result,
        # whichever path produced it, is annotated with embedded entity
        # candidates and descriptive-subject flags before it leaves the
        # parser.
        result.entity_candidates = self._detect_entity_candidates(original, result.subjects)
        result.descriptive_subjects = self._flag_descriptive_subjects(original, result.subjects)
        return result
    
    def _match_patterns(self, normalized: str, original: str) -> Optional[ParseResult]:
        """
        Run the pattern table against normalised text.
        Returns None when no pattern produces a usable result.
        """
        for rule in self.patterns:
            match = re.match(rule.pattern, normalized, re.IGNORECASE)
            if match:
                extractor = getattr(self, rule.extractor, None)
                if extractor:
                    result = extractor(match, original, rule.statement_type)
                    if result.status in (ParseStatus.SUCCESS, ParseStatus.PARTIAL):
                        return result
        return None
    
    _PARENTHETICAL = re.compile(r"^([^,]+?),\s+([^,]+?),\s+(.+)$")
    
    def _reduce_parenthetical(self, normalized: str) -> Optional[Tuple[str, str]]:
        """
        Remove one comma-delimited subordinate clause inserted between
        the subject and the main verb (defect P1-B).

        'aspirin, discovered in 1897, is an analgesic' matched no
        pattern and fell to token guessing. Reducing it to the main
        clause 'aspirin is an analgesic' lets the established patterns
        handle it. The removed clause is returned so the caller can
        surface it as unparsed and unverified; the clause content is
        never silently accepted.
        """
        m = self._PARENTHETICAL.match(normalized)
        if not m:
            return None
        reduced = re.sub(r'\s+', ' ', f"{m.group(1)} {m.group(3)}").strip()
        return reduced, m.group(2)
    
    def _detect_entity_candidates(self, original: str, subjects: List[str]) -> List[str]:
        """
        Detect capitalised entity candidates the parser did not extract
        (defect P1-C).

        Embedded entities in non-subject positions (for example
        'Sherlock Holmes' in 'Aspirin was not invented by Sherlock
        Holmes.') were never checked and the pipeline passed silently.
        This detector surfaces them so the pipeline can flag what was
        NOT verified. It does not attempt multi-entity claim extraction;
        that remains the CONTRIBUTING-flagged research problem.
        """
        runs = re.findall(r"\b[A-Z][A-Za-z0-9'\-]*(?:\s+[A-Z][A-Za-z0-9'\-]*)*", original)
        subjects_lc = [s.lower() for s in subjects]
        candidates: List[str] = []
        for run in runs:
            words = run.split()
            # Drop leading words capitalised for orthographic reasons only.
            while words and words[0].lower() in self._CANDIDATE_STOPWORDS:
                words = words[1:]
            if not words:
                continue
            candidate = ' '.join(words)
            candidate_lc = candidate.lower()
            if candidate_lc in self._CANDIDATE_STOPWORDS:
                continue
            # Already extracted as, or contained within, a subject.
            if any(candidate_lc == s or candidate_lc in s for s in subjects_lc):
                continue
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates
    
    def _flag_descriptive_subjects(self, original: str, subjects: List[str]) -> List[str]:
        """
        Flag subjects that are descriptive noun phrases rather than
        entity constants (defect P1-D).

        'The capital of France is Paris.' extracts the descriptive
        phrase 'capital of france' as its subject. A corpus lookup on
        that phrase is meaningless, so the refusal must state the v0.1
        parser scope reason rather than read as a plain corpus miss.

        Heuristic: the phrase contains ' of ' and, in the original text,
        at least one non-particle word is lower case. This rules out
        proper compounds such as 'United States of America'. Definite
        description treatment in NTP is itself PRELIMINARY (not yet
        validated from source), so refusing here is the theoretically
        safe v0.1 behaviour.
        """
        particles = {"of", "the", "a", "an"}
        flagged: List[str] = []
        for subject in subjects:
            if " of " not in f" {subject} ":
                continue
            pattern = r"\b" + r"\s+".join(re.escape(w) for w in subject.split()) + r"\b"
            match = re.search(pattern, original, re.IGNORECASE)
            span_words = match.group(0).split() if match else subject.split()
            content_words = [w for w in span_words if w.lower() not in particles]
            if any(w[:1].islower() for w in content_words):
                flagged.append(subject)
        return flagged
    
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
        """Extract: 'All X are Y' â†’ âˆ€x(X(x) âŠƒ Y(x))"""
        subject_class = self._to_predicate_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        var = self._fresh_var()
        
        # âˆ€x(SubjectClass(x) âŠƒ Predicate(x))
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
        """Extract: 'No X are Y' â†’ âˆ€x(X(x) âŠƒ ~Y(x))"""
        subject_class = self._to_predicate_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        var = self._fresh_var()
        
        # âˆ€x(SubjectClass(x) âŠƒ ~Predicate(x))
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
        """Extract: 'Some X are Y' â†’ âˆƒx(X(x) âˆ§ Y(x))"""
        subject_class = self._to_predicate_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        var = self._fresh_var()
        
        # âˆƒx(SubjectClass(x) âˆ§ Predicate(x))
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
        """Extract: 'Some X are not Y' â†’ âˆƒx(X(x) âˆ§ ~Y(x))"""
        subject_class = self._to_predicate_name(match.group(1))
        predicate = self._to_predicate_name(match.group(2))
        var = self._fresh_var()
        
        # âˆƒx(SubjectClass(x) âˆ§ ~Predicate(x))
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
        """Extract: 'X is Y' â†’ Y(x) where x is the subject"""
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
        """Extract: 'X is not Y' â†’ ~Y(x)"""
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
        """Extract: 'If P then Q' â†’ P âŠƒ Q (recursively parsed)"""
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
        """Extract: 'P and Q' â†’ P âˆ§ Q"""
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
        """Extract: 'P or Q' â†’ P âˆ¨ Q"""
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
        """Extract: 'What is the X of Y?' â†’ Query for X(Y)"""
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
            # Normalise the subject token so trailing punctuation is not
            # captured into it (defect P1-A).
            subject = self._clean_subject_token(words[0])
            predicate = '_'.join(words[1:])
            
            if subject:
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
    1. Parse natural language â†’ NTP Formula
    2. Analyze formula â†’ Existential loading characteristic
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
            status = "âœ“ PASS"
        else:
            failed += 1
            status = "âœ— FAIL"
        
        print(f"[{status}] \"{text}\"")
        print(f"  Type: {result.statement_type.name} (expected: {expected_type.name}) {'âœ“' if type_match else 'âœ—'}")
        if result.formula:
            print(f"  Formula: {result.formula}")
            if actual_char:
                print(f"  Characteristic: {actual_char.value} (expected: {expected_char.value if expected_char else 'N/A'}) {'âœ“' if char_match else 'âœ—'}")
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
            print(f"Rule Chain: {' â†’ '.join(result['analysis']['rule_chain'])}")
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
    print("â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—")
    print("â•‘     V.E.R.A. - Verified Existence and Reason Architecture        â•‘")
    print("â•‘                    Formula Parser v0.1.0                          â•‘")
    print("â•‘                                                                    â•‘")
    print("â•‘  Converting natural language to NTP formulas                      â•‘")
    print("â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•")
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
