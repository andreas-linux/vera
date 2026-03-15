"""
V.E.R.A. — Verified Existence and Reasoning Architecture
=========================================================

An open-source AI verification system that eliminates hallucinations
by formally separating predication (ℳ) from existence (E!).

Grounded in Non-Traditional Predication Theory (NTP),
developed by Professor Horst Wessel, Humboldt University Berlin.

Source: Wessel, H. (1992). 'Existenz, Ununterscheidbarkeit, Identität.'
        Wissenschaftliche Zeitschrift der Humboldt-Universität zu Berlin.

Version: 0.1.0
Licence: GPL-3.0
"""

__version__ = "0.1.0"
__author__ = "V.E.R.A. Open Source Initiative"
__licence__ = "GPL-3.0"

from .krampitz_analyzer import KrampitzAnalyzer, Characteristic
from .e_verification_service import EVerificationService, ExistenceStatus, ExistenceResult
from .vera_pipeline import VERAPipeline, VerificationOutcome, VerifiedResponse

__all__ = [
    "KrampitzAnalyzer",
    "Characteristic",
    "EVerificationService",
    "ExistenceStatus",
    "ExistenceResult",
    "VERAPipeline",
    "VerificationOutcome",
    "VerifiedResponse",
]
