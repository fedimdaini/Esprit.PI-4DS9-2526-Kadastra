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


def clean_line_breaks(text):
    """
    Join words that were broken across lines by LLM fixed-width wrapping.
    Preserves paragraph breaks (double newlines).
    """
    if not text:
        return text
    text = text.replace('\r\n', '\n')
    # Normalize 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Replace single newlines (not paragraph breaks) with a space
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    # Clean up multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    return text


def post_correct_contract(contract_text):
    """
    Post-process a generated contract:
    1. Fix broken words from LLM line wrapping
    2. Apply grammar corrections paragraph by paragraph.
    """
    if not contract_text:
        return contract_text

    # Step 1: Fix broken line wrapping
    contract_text = clean_line_breaks(contract_text)

    # Step 2: Grammar corrections per paragraph
    paragraphs = contract_text.split('\n')
    corrected_parts = []
    for para in paragraphs:
        if para.strip():
            corrected_parts.append(correct_text_enhanced(para))
        else:
            corrected_parts.append(para)
    return '\n'.join(corrected_parts)
