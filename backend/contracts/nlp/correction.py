"""
NLP 5 — Grammar correction (regex-based, no Java/LanguageTool needed).
Applied on both input text and generated contracts.
"""
import re
from .config import GRAMMAR_FIXES_FR


def correct_text_enhanced(text):
    """Apply regex-based grammar corrections for common French/Tunisian typos."""
    result = text
    for pattern, replacement in GRAMMAR_FIXES_FR:
        result = re.sub(pattern, replacement, result)
    return result


def post_correct_contract(contract_text):
    """
    Post-process a generated contract with grammar corrections.
    Handles long texts by processing paragraph by paragraph.
    """
    if not contract_text:
        return contract_text

    paragraphs = contract_text.split('\n')
    corrected_parts = []
    for para in paragraphs:
        if para.strip():
            corrected_parts.append(correct_text_enhanced(para))
        else:
            corrected_parts.append(para)
    return '\n'.join(corrected_parts)
