"""
PDF Generator — Creates professional contract PDFs using fpdf2.
"""
import os
import re
import unicodedata
from fpdf import FPDF
from fpdf.enums import XPos, YPos


def clean_text_for_pdf(text):
    """Clean text for PDF compatibility."""
    replacements = [
        ('\u2014', '-'), ('\u2013', '-'),
        ('\u2019', "'"), ('\u2018', "'"),
        ('\u201c', '"'), ('\u201d', '"'),
        ('\u2022', '-'), ('\u2026', '...'),
        ('\u00a0', ' '),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    text = unicodedata.normalize('NFKD', text)
    return re.sub(r'[^\x20-\x7E\t\n\xC0-\xFF]', '', text)


def safe_text(text, max_len=95):
    """Word-wrap long lines for PDF, respecting word boundaries."""
    result = []
    for line in text.split('\n'):
        if len(line) <= max_len:
            result.append(line)
            continue
        words = line.split(' ')
        current_line = ''
        for word in words:
            if current_line and len(current_line) + 1 + len(word) > max_len:
                result.append(current_line)
                current_line = word
            else:
                current_line = (current_line + ' ' + word) if current_line else word
        if current_line:
            result.append(current_line)
    return '\n'.join(result)


def generate_pdf_contract(contract_text, listing, contract_type,
                          model_label='LLM', nlp_report=None,
                          output_dir=None):
    """
    Generate a professional PDF contract.
    Returns the file path to the generated PDF.
    """
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'contracts_pdf'
        )
    os.makedirs(output_dir, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Draw a thin border around the page
    pdf.set_draw_color(180, 180, 180)
    pdf.rect(5, 5, 200, 287)

    # Header
    pdf.set_font('Times', 'B', 24)
    pdf.set_text_color(20, 20, 50)
    pdf.cell(0, 15, 'KADASTRA LEGAL', align='C',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font('Times', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(
        0, 5,
        'Document genere par Intelligence Artificielle - Certification Kadastra NLP 7/7',
        align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )

    # Separator line
    pdf.set_draw_color(40, 40, 80)
    pdf.line(20, pdf.get_y() + 4, 190, pdf.get_y() + 4)
    pdf.ln(10)

    # Title
    pdf.set_font('Times', 'B', 16)
    pdf.set_text_color(0, 0, 0)
    titles = {
        'vente': 'PROMESSE SYNALLAGMATIQUE DE VENTE IMMOBILIERE',
        'location': "CONTRAT DE BAIL A USAGE D'HABITATION",
        'terrain': 'CONTRAT DE CESSION DE TERRAIN',
    }
    pdf.cell(
        0, 10,
        titles.get(contract_type, "ACTE JURIDIQUE IMMOBILIER"),
        align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.ln(6)

    # Contract body
    pdf.set_font('Times', '', 11)
    cleaned = safe_text(clean_text_for_pdf(contract_text))
    for line in cleaned.split('\n'):
        if not line.strip():
            pdf.ln(4)
            continue
        
        # Section headers (Article X, ARTICLE X, or all caps > 5 chars)
        is_header = (
            line.strip().upper() == line.strip() and len(line.strip()) > 5
        ) or line.strip().lower().startswith('article')

        if is_header:
            pdf.ln(2)
            pdf.set_font('Times', 'B', 12)
            pdf.set_text_color(30, 30, 80)
            pdf.multi_cell(0, 7, line.strip(),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font('Times', '', 11)
            pdf.set_text_color(0, 0, 0)
        else:
            pdf.multi_cell(0, 6, line.strip(),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Footer
    pdf.set_y(-20)
    pdf.set_font('Times', 'I', 8)
    pdf.set_text_color(150, 150, 150)
    ccr_nlp = nlp_report.get('ccr_nlp', '?') if nlp_report else '?'
    pdf.cell(0, 10, f'Ref: KAD-{listing.get("id", "X")}-{model_label} | Qualite Juridique: {ccr_nlp}%', align='C')

    # Output path
    listing_id = listing.get('id', 'x')
    output_path = os.path.join(
        output_dir, f'contrat_{contract_type}_{listing_id}.pdf'
    )
    pdf.output(output_path)
    return output_path
