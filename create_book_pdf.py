"""Combine rewritten chapters into a single PDF book"""
import os
import glob
import re
from datetime import datetime

# Try to use reportlab for PDF generation
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    PDF_LIB = "reportlab"
except ImportError:
    PDF_LIB = None

def get_chapter_files():
    """Get all chapter files sorted by number"""
    pattern = os.path.join("rewrites", "chapter_*.md")
    files = glob.glob(pattern)
    # Sort by chapter number
    files.sort(key=lambda f: int(re.search(r'chapter_(\d+)', f).group(1)))
    return files

def parse_chapter_file(filepath):
    """Parse a chapter file and extract title and content"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract title from first line (## Chapter X: Title)
    title_match = re.match(r'^##\s+(.+?)$', content.strip(), re.MULTILINE)
    title = title_match.group(1) if title_match else os.path.basename(filepath)

    # Remove the title line for body processing
    body = re.sub(r'^##\s+.+?\n', '', content.strip(), flags=re.MULTILINE)

    return title, body

def convert_markdown_to_plain(text):
    """Convert basic markdown to plain text for PDF"""
    # Remove full chapter headers
    text = re.sub(r'^##+\s+.+?$', '', text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'\*', '', text)
    # Remove links
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Clean up extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def create_pdf_with_reportlab(chapters, output_path, page_size=None):
    """Create PDF using reportlab"""
    from reportlab.lib.pagesizes import letter
    page_size = page_size or letter
    doc = SimpleDocTemplate(
        output_path,
        pagesize=page_size,
        rightMargin=72, leftMargin=72,
        topMargin=72, bottomMargin=72
    )

    styles = getSampleStyleSheet()

    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        keepWithNext=True
    )

    # Chapter title style
    chapter_style = ParagraphStyle(
        'ChapterTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        spaceBefore=30,
        keepWithNext=True
    )

    # Body text style
    body_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        spaceAfter=12,
        alignment=TA_LEFT
    )

    # Quote style
    quote_style = ParagraphStyle(
        'Quote',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        spaceAfter=12,
        leftIndent=20,
        fontName='Times-Italic'
    )

    story = []

    # Add title page
    story.append(Paragraph("Gene is Missing", title_style))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", body_style))

    story.append(PageBreak())

    # Add chapters
    for i, (title, content) in enumerate(chapters):
        # Add chapter title
        story.append(Paragraph(title, chapter_style))

        # Convert and add content
        plain_text = convert_markdown_to_plain(content)

        # Split into paragraphs and add to story
        for para in plain_text.split('\n\n'):
            if para.strip():
                if para.strip().startswith('"') and para.strip().endswith('"'):
                    # Dialogue - format as quote
                    clean_para = para.strip().strip('"')
                    story.append(Paragraph(f'"{clean_para}"', quote_style))
                else:
                    story.append(Paragraph(para, body_style))

        # Add page break between chapters (except last)
        if i < len(chapters) - 1:
            story.append(PageBreak())

    doc.build(story)
    return output_path

def create_simple_text_pdf(chapters, output_path):
    """Create a simple text-based PDF using basic Python"""
    # This is a fallback if reportlab is not available
    # Create a simple text file instead
    text_path = output_path.replace('.pdf', '.txt')

    with open(text_path, 'w', encoding='utf-8') as f:
        f.write("BOOK TITLE\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%B %d, %Y')}\n\n")
        f.write("=" * 50 + "\n\n")

        for title, content in chapters:
            f.write(f"\n{title}\n")
            f.write("-" * 40 + "\n\n")
            plain_text = convert_markdown_to_plain(content)
            f.write(plain_text)
            f.write("\n\n")

    return text_path

def main():
    print("Combining chapters into PDF...")

    # Get all chapter files
    chapter_files = get_chapter_files()
    print(f"Found {len(chapter_files)} chapter files")

    if not chapter_files:
        print("No chapter files found in rewrites/ directory")
        return

    # Parse all chapters
    chapters = []
    for filepath in chapter_files:
        title, content = parse_chapter_file(filepath)
        chapters.append((title, content))
        print(f"  - {title}")

    # Determine output path
    output_path = "rewrites/book.pdf"

    # Create PDF
    if PDF_LIB == "reportlab":
        print(f"\nCreating PDF with reportlab...")
        create_pdf_with_reportlab(chapters, output_path)
        print(f"PDF created: {output_path}")
    else:
        print(f"\nReportlab not available. Creating text file instead...")
        text_path = create_simple_text_pdf(chapters, output_path)
        print(f"Text file created: {text_path}")
        print("Install reportlab for proper PDF: pip install reportlab")

if __name__ == "__main__":
    main()
