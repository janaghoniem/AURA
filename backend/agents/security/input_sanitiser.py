"""
INPUT SANITISER — DiD Layer 1
Checks raw user input before it reaches the LLM.
Called from: language_agent.py → handle_user_input()

Checks applied (in order):
  S-04  Length cap        — truncate first so all later checks see bounded text
  S-05  Unicode normalise — NFKC + confusables map (Cyrillic lookalikes → ASCII)
  S-01  Override keywords — injection phrases
  S-02  Base64 decode     — re-check decoded content for S-01 patterns
  S-03  Delimiters        — ChatML / role tokens
"""

import re
import base64
import unicodedata
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

# ─── Result object ────────────────────────────────────────────────────────────

@dataclass
class SanitisationResult:
    original_text: str
    clean_text: str
    was_blocked: bool = False
    was_modified: bool = False
    risk_level: str = "LOW"          # LOW | MEDIUM | HIGH | CRITICAL
    triggered_checks: List[str] = field(default_factory=list)
    block_reason: str = ""

# ─── Constants ───────────────────────────────────────────────────────────────

MAX_LENGTH = 4096

# S-01: Instruction override / role hijack patterns
OVERRIDE_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above|your)\s+",
    r"forget\s+(everything|all\s+instructions?|your\s+instructions?)",
    r"new\s+system\s+prompt",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if\s+you\s+(are|have)|a\s+)",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"(reveal|show|output|print|display)\s+(the\s+)?(password|api.?key|secret|token|mongodb|database\s+uri)",
    r"(bypass|override|disable)\s+(your\s+)?(safety|security|filter|restriction)",
    r"from\s+now\s+on\s+(you\s+are|ignore)",
    r"your\s+(true\s+)?instructions?\s+(are|is)\s+",
]

# S-03: Prompt role delimiter tokens
DELIMITER_PATTERNS = [
    r"<\|system\|>",
    r"<\|user\|>",
    r"<\|assistant\|>",
    r"\[INST\]",
    r"<<SYS>>",
    r"\[/INST\]",
    r"<</SYS>>",
]

# S-05: Confusables map — visually identical characters that NFKC does NOT collapse
# Maps lookalike Unicode chars → their ASCII equivalent for pattern matching only
# (we normalise a COPY for matching; the user's clean_text keeps NFKC form)
CONFUSABLES = {
    # Cyrillic → Latin
    '\u0456': 'i',   # і  Cyrillic Byelorussian-Ukrainian I  → i
    '\u0430': 'a',   # а  Cyrillic Small Letter A            → a
    '\u0435': 'e',   # е  Cyrillic Small Letter IE           → e
    '\u043e': 'o',   # о  Cyrillic Small Letter O            → o
    '\u0440': 'r',   # р  Cyrillic Small Letter ER           → r
    '\u0441': 'c',   # с  Cyrillic Small Letter ES           → c
    '\u0445': 'x',   # х  Cyrillic Small Letter HA          → x
    '\u0455': 's',   # ѕ  Cyrillic Small Letter DZE         → s
    '\u0440': 'r',   # р  Cyrillic Small Letter ER           → r
    '\u0443': 'y',   # у  Cyrillic Small Letter U            → y
    # Greek → Latin
    '\u03b1': 'a',   # α  Greek Small Letter Alpha           → a
    '\u03b5': 'e',   # ε  Greek Small Letter Epsilon         → e
    '\u03bf': 'o',   # ο  Greek Small Letter Omicron         → o
    '\u03c1': 'p',   # ρ  Greek Small Letter Rho             → p
    '\u03bd': 'v',   # ν  Greek Small Letter Nu              → v
    # Fullwidth → ASCII
    '\uff49': 'i',   # ｉ Fullwidth Latin Small Letter I     → i
    '\uff41': 'a',   # ａ Fullwidth Latin Small Letter A     → a
}


# ─── InputSanitiser class ─────────────────────────────────────────────────────

class InputSanitiser:
    """
    Runs S-01 through S-05 checks on raw user input.
    Returns a SanitisationResult — caller decides what to do with it.

    Check order (important):
      S-04 first  → truncate to MAX_LENGTH so all later checks see bounded text
      S-05 second → unicode normalise + confusables mapping
      S-01 third  → keyword patterns (on normalised text)
      S-02 fourth → base64 decode and re-check
      S-03 fifth  → delimiter tokens
    """

    def sanitise(self, text: str) -> SanitisationResult:
        result = SanitisationResult(
            original_text=text,
            clean_text=text
        )

        # ── S-04 FIRST: truncate so all later checks see bounded input ────────
        # This means a length-bomb injection suffix gets cut off before S-01 sees it
        self._s04_length(result)

        # ── S-05: Unicode normalise (NFKC) + confusables map ─────────────────
        self._s05_unicode_normalise(result)
        if result.was_blocked:
            return result

        # ── S-01: Override / role-hijack keywords ─────────────────────────────
        self._s01_override_keywords(result)
        if result.was_blocked:
            return result

        # ── S-02: Base64 encoded payload ──────────────────────────────────────
        self._s02_base64(result)
        if result.was_blocked:
            return result

        # ── S-03: Prompt delimiter tokens ────────────────────────────────────
        self._s03_delimiters(result)

        # ── Final risk level ──────────────────────────────────────────────────
        if result.was_blocked:
            result.risk_level = "CRITICAL"
        elif result.was_modified:
            result.risk_level = "MEDIUM"
        else:
            result.risk_level = "LOW"

        return result

    # ── S-04 ─────────────────────────────────────────────────────────────────

    def _s04_length(self, result: SanitisationResult):
        """Truncate input that exceeds MAX_LENGTH. Runs FIRST."""
        if len(result.clean_text) > MAX_LENGTH:
            original_len = len(result.clean_text)
            result.clean_text = result.clean_text[:MAX_LENGTH] + " [INPUT TRUNCATED]"
            result.was_modified = True
            result.triggered_checks.append(f"S-04:truncated({original_len}→{MAX_LENGTH})")
            logger.warning(f"✂️  S-04: Input truncated {original_len} → {MAX_LENGTH} chars")

    # ── S-05 ─────────────────────────────────────────────────────────────────

    def _s05_unicode_normalise(self, result: SanitisationResult):
        """
        Two-pass normalisation:
          Pass 1 — NFKC (handles composed forms, fullwidth, etc.)
          Pass 2 — Confusables map (Cyrillic/Greek lookalikes NFKC doesn't collapse)

        We store the normalised text in clean_text so downstream checks use it.
        We also keep a 'match_text' (fully ASCII-folded) used only for S-01 matching.
        """
        original = result.clean_text

        # Pass 1: NFKC
        nfkc = unicodedata.normalize("NFKC", original)

        # Pass 2: confusables map on the NFKC result
        mapped = ''.join(CONFUSABLES.get(c, c) for c in nfkc)

        if mapped != original:
            result.was_modified = True
            result.triggered_checks.append("S-05:unicode_normalise")
            logger.info(f"🔤 S-05: Unicode normalised (original had homoglyphs/composed chars)")
            logger.info(f"   Before: {repr(original[:60])}")
            logger.info(f"   After : {repr(mapped[:60])}")

        # Store fully-mapped version as clean_text so S-01 can match it
        result.clean_text = mapped

    # ── S-01 ─────────────────────────────────────────────────────────────────

    def _s01_override_keywords(self, result: SanitisationResult):
        """Check for instruction override / role hijack phrases."""
        text_lower = result.clean_text.lower()
        for pattern in OVERRIDE_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                result.was_blocked = True
                result.block_reason = f"S-01: Injection keyword matched: '{pattern}'"
                result.triggered_checks.append("S-01:override_keyword")
                logger.warning(f"🚫 S-01 BLOCKED — pattern: {pattern}")
                logger.warning(f"   Input preview: {result.clean_text[:100]}")
                return

    # ── S-02 ─────────────────────────────────────────────────────────────────

    def _s02_base64(self, result: SanitisationResult):
        """Detect base64-encoded injections by decoding and re-scanning."""
        candidates = re.findall(r'[A-Za-z0-9+/]{20,}={0,2}', result.clean_text)
        for candidate in candidates:
            try:
                padded = candidate + "=" * (4 - len(candidate) % 4)
                decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
                decoded_lower = decoded.lower()
                for pattern in OVERRIDE_PATTERNS:
                    if re.search(pattern, decoded_lower, re.IGNORECASE):
                        result.was_blocked = True
                        result.block_reason = (
                            f"S-02: Base64-encoded injection detected "
                            f"(decoded: '{decoded[:60]}...')"
                        )
                        result.triggered_checks.append("S-02:base64_injection")
                        logger.warning(f"🚫 S-02 BLOCKED — base64 decoded to injection")
                        logger.warning(f"   Decoded: {decoded[:100]}")
                        return
            except Exception:
                pass

    # ── S-03 ─────────────────────────────────────────────────────────────────

    def _s03_delimiters(self, result: SanitisationResult):
        """Detect prompt role delimiter tokens (ChatML, Llama, etc.)."""
        for pattern in DELIMITER_PATTERNS:
            if re.search(pattern, result.clean_text, re.IGNORECASE):
                result.was_blocked = True
                result.block_reason = f"S-03: Prompt delimiter token detected: '{pattern}'"
                result.triggered_checks.append("S-03:delimiter")
                logger.warning(f"🚫 S-03 BLOCKED — delimiter: {pattern}")
                return


# ─── Module-level singleton + public function ─────────────────────────────────

_sanitiser = InputSanitiser()

def sanitise_input(text: str) -> SanitisationResult:
    """
    Public entry point — import and call this from language_agent.py.

    Usage in language_agent.py:
        from agents.security.input_sanitiser import sanitise_input
        result = sanitise_input(input_text)
        if result.was_blocked:
            # return early with rejection message
    """
    return _sanitiser.sanitise(text)