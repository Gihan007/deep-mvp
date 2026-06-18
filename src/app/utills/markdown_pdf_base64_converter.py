from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, 
                                TableStyle, PageBreak, Preformatted, 
                                Image as RLImage, KeepTogether, HRFlowable)
from reportlab.platypus.doctemplate import LayoutError
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from datetime import datetime
import re
import base64
from pathlib import Path
from typing import Optional
from reportlab.lib.utils import ImageReader
import io

# Optional dependency (already in requirements.txt)
try:
    from PyPDF2 import PdfReader, PdfWriter
    _PYPDF2_AVAILABLE = True
except Exception:
    PdfReader = None
    PdfWriter = None
    _PYPDF2_AVAILABLE = False


def _trim_pdf_pages_inplace(pdf_path: Path, max_pages: int) -> None:
    """Trim a PDF to the first `max_pages` pages (in-place).

    This is used to enforce a hard page limit (e.g., 2 pages: cover + 1 page body)
    even if markdown content is long.
    """
    if not _PYPDF2_AVAILABLE:
        return
    if max_pages is None or max_pages <= 0:
        return

    try:
        reader = PdfReader(str(pdf_path))
        writer = PdfWriter()
        keep = min(max_pages, len(reader.pages))
        for i in range(keep):
            writer.add_page(reader.pages[i])

        tmp_path = pdf_path.with_suffix(pdf_path.suffix + ".tmp")
        with open(tmp_path, "wb") as f:
            writer.write(f)
        tmp_path.replace(pdf_path)
    except Exception:
        # Never fail the main flow due to trimming issues
        return


def get_logo_path():
    """Return the path to the app logo located at app/media_files/logo.png"""
    # __file__ is .../src/app/utills/markdown_pdf_base64_converter_for_deep_agent.py
    # app folder is parent of utills
    app_dir = Path(__file__).resolve().parent.parent
    return app_dir / "media_files" / "logo.png"


class NumberedCanvas(canvas.Canvas):
    """Custom canvas to add headers and footers"""
    
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        # Keep a textual fallback just in case logo isn't found
        self.company_name = "VinVest"
        self.report_title = "Investment Analysis Report"
        # Load logo once for reuse in headers
        self.logo_reader = None
        self.header_logo_w = None
        self.header_logo_h = None
        self._load_logo()

    def _load_logo(self):
        try:
            path = get_logo_path()
            if path.exists():
                reader = ImageReader(str(path))
                iw, ih = reader.getSize()
                # Size constraints for header logo
                max_w = 1.0 * inch
                max_h = 0.25 * inch
                if iw and ih:
                    scale = min(max_w / iw, max_h / ih)
                else:
                    scale = 1.0
                self.header_logo_w = iw * scale if iw else max_w
                self.header_logo_h = ih * scale if ih else max_h
                self.logo_reader = reader
        except Exception:
            # Fail silently and fallback to text
            self.logo_reader = None
            self.header_logo_w = None
            self.header_logo_h = None

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        """Draw header and footer on each page"""
        page_num = self._pageNumber

        page_w, page_h = self._pagesize
        
        # Skip header/footer on first page (cover page)
        if page_num == 1:
            return
        
        # Header
        self.saveState()
        self.setStrokeColor(colors.HexColor('#1e3a5f'))
        self.setLineWidth(2)
        self.line(0.75*inch, page_h - 0.6*inch, page_w - 0.75*inch, page_h - 0.6*inch)
        
        # Company logo in header (fallback to text if logo missing)
        if self.logo_reader and self.header_logo_w and self.header_logo_h:
            try:
                x = 0.75 * inch
                # Place logo slightly above the header line to avoid overlap
                y = page_h - 0.57*inch
                self.drawImage(self.logo_reader, x, y, width=self.header_logo_w, height=self.header_logo_h, mask='auto')
            except Exception:
                # Fallback to text if drawing fails
                self.setFont('Helvetica-Bold', 10)
                self.setFillColor(colors.HexColor('#1e3a5f'))
                self.drawString(0.75*inch, page_h - 0.5*inch, self.company_name)
        else:
            # Company name in header (text fallback)
            self.setFont('Helvetica-Bold', 10)
            self.setFillColor(colors.HexColor('#1e3a5f'))
            self.drawString(0.75*inch, page_h - 0.5*inch, self.company_name)
        
        # Report title in header (right aligned)
        self.setFont('Helvetica', 9)
        self.setFillColor(colors.HexColor('#5a6c7d'))
        text_width = self.stringWidth(self.report_title, 'Helvetica', 9)
        self.drawString(page_w - 0.75*inch - text_width, page_h - 0.5*inch, self.report_title)
        
        # Footer
        self.setStrokeColor(colors.HexColor('#1e3a5f'))
        self.setLineWidth(1)
        self.line(0.75*inch, 0.65*inch, page_w - 0.75*inch, 0.65*inch)
        
        # Page number
        self.setFont('Helvetica', 9)
        self.setFillColor(colors.HexColor('#5a6c7d'))
        page_text = f"Page {page_num - 1} of {page_count - 1}"
        text_width = self.stringWidth(page_text, 'Helvetica', 9)
        self.drawString(page_w/2 - text_width/2, 0.5*inch, page_text)
        
        # Footer text - left
        self.setFont('Helvetica', 8)
        self.drawString(0.75*inch, 0.5*inch, "Confidential")
        
        # Footer text - right
        date_text = datetime.now().strftime('%B %d, %Y')
        text_width = self.stringWidth(date_text, 'Helvetica', 8)
        self.drawString(page_w - 0.75*inch - text_width, 0.5*inch, date_text)
        
        self.restoreState()


def parse_markdown_table(table_text):
    """Parse a markdown table into a list of lists"""
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    lines = [line for line in lines if not re.match(r'^[\s\|:-]+$', line)]
    
    table_data = []
    for line in lines:
        cells = [cell.strip() for cell in line.split('|')]
        cells = [cell for cell in cells if cell]
        if cells:
            table_data.append(cells)
    
    return table_data


def convert_markdown_formatting(text):
    """Convert markdown formatting to ReportLab HTML tags"""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'\*(?!\*)(.*?)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'_(?!_)(.*?)_(?!_)', r'<i>\1</i>', text)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<link href="\2" color="blue">\1</link>', text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" size="10" backColor="#f5f5f5">\1</font>', text)
    
    return text


def create_cover_page(story, title, styles, color_scheme, single_page: bool = False):
    """Create a professional cover page"""
    
    # Large spacer to center content
    story.append(Spacer(1, 1.5*inch))
    
    # Company logo on cover (fallback to text if missing)
    logo_path = get_logo_path()
    if logo_path.exists():
        try:
            reader = ImageReader(str(logo_path))
            iw, ih = reader.getSize()
            max_w = 3.5 * inch
            max_h = 1.2 * inch
            scale = min(max_w / iw, max_h / ih) if iw and ih else 1.0
            w = iw * scale
            h = ih * scale
            logo_img = RLImage(str(logo_path), width=w, height=h)
            logo_img.hAlign = 'CENTER'
            story.append(logo_img)
            story.append(Spacer(1, 0.2*inch))
        except Exception:
            company_style = ParagraphStyle(
                'CompanyName',
                parent=styles['Normal'],
                fontSize=32,
                textColor=colors.HexColor(color_scheme['primary']),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=20,
                leading=38
            )
            story.append(Paragraph("VinVest", company_style))
    else:
        # Fallback to typed company name if logo not found
        company_style = ParagraphStyle(
            'CompanyName',
            parent=styles['Normal'],
            fontSize=32,
            textColor=colors.HexColor(color_scheme['primary']),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=20,
            leading=38
        )
        story.append(Paragraph("VinVest", company_style))
    
    # Tagline
    tagline_style = ParagraphStyle(
        'Tagline',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#5a6c7d'),
        alignment=TA_CENTER,
        spaceAfter=35,
        fontName='Helvetica-Oblique',
        leading=18
    )
    story.append(Paragraph("Professional Investment Analysis", tagline_style))
    
    # Divider line
    story.append(HRFlowable(width="50%", thickness=2, 
                           color=colors.HexColor(color_scheme['accent']),
                           spaceBefore=20, spaceAfter=20))
    
    # Report title
    report_title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=22,
        textColor=colors.HexColor(color_scheme['primary']),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=25
    )
    story.append(Paragraph(title, report_title_style))
    
    # Date
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#5a6c7d'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", date_style))
    
    # Page break after cover (skip for single-page PDFs)
    if not single_page:
        story.append(PageBreak())


def _estimate_single_page_height(markdown_text: str, inline_images: Optional[list] = None) -> float:
    """Heuristic height estimation for a single tall PDF page.

    We deliberately over-estimate to avoid ReportLab spilling into page 2.
    """
    base = letter[1]  # at least one letter page
    # crude line estimate: 1 line per markdown line + extra for long lines
    lines = markdown_text.splitlines() if markdown_text else [""]
    approx_lines = 0
    for ln in lines:
        # assume ~95 chars per line in PDF body
        approx_lines += max(1, (len(ln) // 95) + 1)

    # Each line ~ 13pt in our compact body style
    content_h = approx_lines * 13

    # Tables and headings tend to be taller; add a safety factor
    content_h *= 1.25

    # Images can be large; add budget per inline image
    img_extra = 0
    if inline_images:
        img_extra = len(inline_images) * (4.0 * inch)

    # Cover content estimate
    cover_extra = 7.0 * inch

    # Clamp to a maximum to avoid absurd sizes
    max_h = 500 * inch
    return float(min(max_h, max(base, content_h + img_extra + cover_extra)))


def _calc_story_height(story: list, avail_width: float) -> float:
    """Compute approximate required height to render `story` on a single page.

    Uses Flowable.wrap() to measure heights. Unwraps KeepTogether to avoid
    double-counting and to get more accurate totals.
    """

    def _flowable_height(flowable) -> float:
        # Unwrap KeepTogether content if possible
        try:
            if hasattr(flowable, "_content") and isinstance(getattr(flowable, "_content"), list):
                return sum(_flowable_height(f) for f in flowable._content)
        except Exception:
            pass

        # Spacer
        if hasattr(flowable, "height") and isinstance(getattr(flowable, "height"), (int, float)):
            return float(flowable.height)

        # General case
        try:
            _w, h = flowable.wrap(avail_width, 10_000_000)
            return float(h or 0)
        except Exception:
            return 0.0

    return float(sum(_flowable_height(f) for f in story))


def _pdf_page_count(pdf_bytes: bytes) -> Optional[int]:
    """Count pages in a PDF byte-string using PyPDF2 (if available)."""
    if not _PYPDF2_AVAILABLE:
        return None
    try:
        import io as _io

        r = PdfReader(_io.BytesIO(pdf_bytes))
        return len(r.pages)
    except Exception:
        return None


def _render_pdf_bytes(
    story: list,
    *,
    pagesize,
    topMargin,
    bottomMargin,
    leftMargin,
    rightMargin,
) -> bytes:
    """Render story into a PDF byte string (in-memory)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=pagesize,
        topMargin=topMargin,
        bottomMargin=bottomMargin,
        leftMargin=leftMargin,
        rightMargin=rightMargin,
    )
    # doc.build mutates the list, so use a shallow copy
    doc.build(list(story), canvasmaker=NumberedCanvas)
    return buf.getvalue()


def _fit_single_page_height(
    story: list,
    *,
    page_w: float,
    min_h: float,
    initial_h: float,
    max_h: float,
    topMargin,
    bottomMargin,
    leftMargin,
    rightMargin,
    max_grow_steps: int = 10,
    refine_steps: int = 8,
) -> float:
    """Find the minimal page height that renders `story` in exactly 1 page.

    Strategy:
    1) Grow height until the PDF is 1 page.
    2) Binary-search down to minimize bottom whitespace.
    """
    if not _PYPDF2_AVAILABLE:
        return initial_h

    def pages_for(h: float) -> Optional[int]:
        try:
            pdf = _render_pdf_bytes(
                story,
                pagesize=(page_w, h),
                topMargin=topMargin,
                bottomMargin=bottomMargin,
                leftMargin=leftMargin,
                rightMargin=rightMargin,
            )
            return _pdf_page_count(pdf)
        except LayoutError:
            # If the story contains an unbreakable block (e.g., KeepTogether-wrapped
            # table/image) that cannot fit in the current height, ReportLab can throw
            # a LayoutError during this measurement render. Treat this as "does not fit"
            # so the caller will increase the page height.
            return 999
        except Exception:
            return 999

    h = max(min_h, min(max_h, initial_h))
    p = pages_for(h)

    # If we can't measure, fall back
    if p is None:
        return h

    # Grow until fits 1 page
    grow_steps = 0
    while p > 1 and h < max_h and grow_steps < max_grow_steps:
        h = min(max_h, h * 1.2 + (0.5 * inch))
        p = pages_for(h)
        if p is None:
            return h
        grow_steps += 1

    # If still doesn't fit, just return max
    if p != 1:
        return h

    # Now refine: find minimal h with 1 page
    low = min_h
    high = h
    for _ in range(refine_steps):
        mid = (low + high) / 2.0
        pmid = pages_for(mid)
        if pmid is None:
            return high
        if pmid <= 1:
            high = mid
        else:
            low = mid
    return high


def get_professional_styles(color_scheme):
    """Create professional paragraph styles with proper hierarchy"""
    styles = getSampleStyleSheet()
    
    # Heading 1 - Major sections
    heading1 = ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor(color_scheme['primary']),
        spaceAfter=10,
        spaceBefore=16,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderColor=colors.HexColor(color_scheme['primary']),
        borderPadding=8,
        backColor=colors.HexColor('#f0f4f8'),
        leftIndent=10,
        keepWithNext=True
    )
    
    # Heading 2 - Subsections
    heading2 = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.HexColor(color_scheme['secondary']),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold',
        leftIndent=5,
        keepWithNext=True,
        borderWidth=0,
        borderColor=colors.HexColor(color_scheme['secondary']),
        borderPadding=0,
        borderRadius=0
    )
    
    # Heading 3 - Minor subsections
    heading3 = ParagraphStyle(
        'CustomHeading3',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor(color_scheme['text_dark']),
        spaceAfter=6,
        spaceBefore=10,
        fontName='Helvetica-Bold',
        keepWithNext=True
    )

    # Heading 4 - Deep subsections (supports markdown ####)
    heading4 = ParagraphStyle(
        'CustomHeading4',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor(color_scheme['text_dark']),
        spaceAfter=4,
        spaceBefore=8,
        fontName='Helvetica-Bold',
        leftIndent=8,
        keepWithNext=True,
    )
    
    # Body text
    body = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leading=13,
        textColor=colors.HexColor('#2c3e50')
    )
    
    # Bullet points
    bullet = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=30,
        spaceAfter=6,
        leading=13,
        textColor=colors.HexColor('#2c3e50'),
        bulletIndent=15
    )
    
    # Code blocks
    code = ParagraphStyle(
        'CustomCode',
        parent=styles['Code'],
        fontSize=8,
        leftIndent=30,
        rightIndent=30,
        spaceAfter=10,
        spaceBefore=10,
        backColor=colors.HexColor('#f8f9fa'),
        fontName='Courier',
        borderWidth=1,
        borderColor=colors.HexColor('#dee2e6'),
        borderPadding=10
    )
    
    # Caption for images
    caption = ParagraphStyle(
        'Caption',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#6c757d'),
        spaceAfter=8,
        spaceBefore=4,
        fontName='Helvetica-Oblique',
        alignment=TA_CENTER
    )
    
    return {
        'heading1': heading1,
        'heading2': heading2,
        'heading3': heading3,
        'heading4': heading4,
        'body': body,
        'bullet': bullet,
        'code': code,
        'caption': caption
    }


def create_professional_table(table_data, color_scheme, available_width: Optional[float] = None):
    """Create a professionally styled table"""

    # ReportLab `Table` does NOT automatically wrap plain strings.
    # To support wrapping (long headers / long values) we must convert
    # each cell into a Flowable (Paragraph) with word-wrapping enabled.
    if not table_data:
        table_data = [[""]]

    # Calculate column widths
    num_cols = len(table_data[0]) if table_data else 1
    aw = float(available_width) if available_width else float(6.5 * inch)
    col_widths = [aw / num_cols] * num_cols

    header_cell_style = ParagraphStyle(
        "TableHeaderCell",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.white,
        alignment=TA_CENTER,
        wordWrap="CJK",  # allows breaking long tokens (no spaces)
        splitLongWords=1,
    )

    body_cell_style = ParagraphStyle(
        "TableBodyCell",
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#2c3e50"),
        alignment=TA_LEFT,
        wordWrap="CJK",
        splitLongWords=1,
    )

    def _cell_para(text: str, style: ParagraphStyle) -> Paragraph:
        # Convert basic markdown in table cells (bold/italic/code/link)
        # and also keep explicit line breaks.
        s = convert_markdown_formatting(str(text or "").replace("\n", "<br/>"))
        return Paragraph(s, style)

    formatted_table_data = []
    for r, row in enumerate(table_data):
        formatted_row = []
        for c in range(num_cols):
            txt = row[c] if c < len(row) else ""
            style = header_cell_style if r == 0 else body_cell_style
            formatted_row.append(_cell_para(txt, style))
        formatted_table_data.append(formatted_row)

    table = Table(formatted_table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    
    # Professional table styling
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(color_scheme['primary'])),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Use TOP valign so wrapped lines expand downward without overlapping
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2c3e50')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        
        # Grid and borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor(color_scheme['primary'])),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor(color_scheme['primary'])),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8f9fa'), colors.white]),
    ]))
    
    return table


def markdown_to_pdf(markdown_text, output_path, title=None, color_scheme=None, inline_images=None, single_page: bool = False):
    """Convert markdown text to a professional PDF with headers and footers"""
    
    # Professional color scheme
    if color_scheme is None:
        color_scheme = {
            'primary': '#1e3a5f',      # Deep blue
            'secondary': '#2c5282',     # Medium blue
            'accent': '#4299e1',        # Bright blue
            'text_dark': '#2d3748',     # Dark gray
            'text_light': '#718096',    # Light gray
            'background': '#f7fafc'     # Very light gray
        }
    
    # Layout compaction knobs
    compact = {
        "top_margin": 0.7 * inch,
        "bottom_margin": 0.7 * inch,
        "left_margin": 0.8 * inch,
        "right_margin": 0.8 * inch,
    }

    # We will create the SimpleDocTemplate later (after story is built) so that
    # in `single_page` mode we can compute the page height precisely and avoid
    # a large empty area at the bottom.
    page_w = letter[0]
    avail_width = page_w - compact["left_margin"] - compact["right_margin"]
    
    # Get styles
    base_styles = getSampleStyleSheet()
    custom_styles = get_professional_styles(color_scheme)
    
    # Build story
    story = []
    
    # Extract title from markdown if not provided
    lines = markdown_text.split('\n')
    if title is None:
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                title = line.replace('#', '').strip()
                break
    
    if not title:
        title = "Investment Analysis Report"
    
    # Create cover page
    create_cover_page(story, title, base_styles, color_scheme, single_page=single_page)
    
    # Process images
    placeholder_re = re.compile(r'^\[fig_description-(.+?)\]$')
    images_by_desc = {}
    if inline_images:
        for item in inline_images:
            try:
                desc_key = (item.get("description") or "").strip()
            except AttributeError:
                desc_key = ""
            images_by_desc.setdefault(desc_key, []).append(item)
    
    def insert_image(item):
        """Insert image with caption"""
        try:
            b64 = None
            desc = ""
            try:
                b64 = item.get("image_base64")
                desc = (item.get("description") or "").strip()
            except AttributeError:
                b64 = item
                desc = ""
            
            if not b64:
                return False
            
            img_bytes = io.BytesIO(base64.b64decode(b64))
            img_reader = ImageReader(img_bytes)
            iw, ih = img_reader.getSize()
            
            # Size constraints
            max_w = 6 * inch
            max_h = 7 * inch
            scale = min(max_w / iw, max_h / ih) if iw and ih else 1.0
            w = iw * scale
            h = ih * scale
            
            img = RLImage(img_bytes, width=w, height=h)
            
            # Keep image and caption together
            img_elements = [
                Spacer(1, 0.1*inch),
                img,
            ]
            
            if desc:
                img_elements.append(Spacer(1, 0.1*inch))
                img_elements.append(Paragraph(convert_markdown_formatting(desc), custom_styles['caption']))
            
            img_elements.append(Spacer(1, 0.2*inch))
            
            story.append(KeepTogether(img_elements))
            return True
        except Exception:
            return False
    
    def insert_image_for_desc(desc_key):
        lst = images_by_desc.get(desc_key)
        if lst:
            item = lst.pop(0)
            return insert_image(item)
        return False
    
    # Process markdown content
    i = 0
    in_table = False
    in_code_block = False
    table_lines = []
    code_lines = []
    title_found = False
    
    while i < len(lines):
        line = lines[i]
        line_stripped = line.strip()
        
        # Handle code blocks
        if line_stripped.startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_lines = []
            else:
                in_code_block = False
                if code_lines:
                    code_text = '\n'.join(code_lines)
                    pre = Preformatted(code_text, custom_styles['code'])
                    story.append(KeepTogether([pre]))
                code_lines = []
            i += 1
            continue
        
        if in_code_block:
            code_lines.append(line)
            i += 1
            continue
        
        # Handle tables
        if '|' in line_stripped and not in_table:
            in_table = True
            table_lines = [line_stripped]
            i += 1
            continue
        
        if in_table:
            if '|' in line_stripped or re.match(r'^[\s\|:-]+$', line_stripped):
                table_lines.append(line_stripped)
                i += 1
                continue
            else:
                in_table = False
                table_text = '\n'.join(table_lines)
                table_data = parse_markdown_table(table_text)
                
                if table_data:
                    table = create_professional_table(table_data, color_scheme, available_width=avail_width)
                    story.append(KeepTogether([table]))
                    story.append(Spacer(1, 0.2*inch))
                
                table_lines = []
                continue
        
        # Skip empty lines
        if not line_stripped:
            if story:
                story.append(Spacer(1, 0.08*inch))
            i += 1
            continue
        
        # Handle figure placeholders
        m = placeholder_re.match(line_stripped)
        if m:
            desc_key = m.group(1).strip()
            insert_image_for_desc(desc_key)
            i += 1
            continue
        
        # Parse headings
        if line_stripped.startswith('# ') and not line_stripped.startswith('##'):
            heading_text_raw = line_stripped[2:].strip()
            if title and heading_text_raw == title and not title_found:
                title_found = True
                i += 1
                continue
            heading_text = convert_markdown_formatting(heading_text_raw)
            story.append(Paragraph(heading_text, custom_styles['heading1']))
        
        elif line_stripped.startswith('## ') and not line_stripped.startswith('###'):
            heading_text = convert_markdown_formatting(line_stripped[3:].strip())
            story.append(Paragraph(heading_text, custom_styles['heading2']))
        
        elif line_stripped.startswith('### '):
            heading_text = convert_markdown_formatting(line_stripped[4:].strip())
            story.append(Paragraph(heading_text, custom_styles['heading3']))

        elif line_stripped.startswith('#### '):
            # Support 4th-level markdown headings (common in LLM output like "#### Moat Assessment")
            heading_text = convert_markdown_formatting(line_stripped[5:].strip())
            story.append(Paragraph(heading_text, custom_styles['heading4']))
        
        # Numbered lists
        elif re.match(r'^\d+\.\s', line_stripped):
            number_text = convert_markdown_formatting(line_stripped)
            story.append(Paragraph(number_text, custom_styles['bullet']))
        
        # Bullet points
        elif line_stripped.startswith('- ') or (line_stripped.startswith('* ') and not line_stripped.startswith('**')):
            bullet_text = convert_markdown_formatting(line_stripped[2:].strip())
            story.append(Paragraph(f"• {bullet_text}", custom_styles['bullet']))
        
        # Horizontal rule
        elif re.match(r'^(\-{3,}|\*{3,}|_{3,})$', line_stripped):
            story.append(Spacer(1, 0.1*inch))
            story.append(HRFlowable(width="100%", thickness=1, 
                                   color=colors.HexColor(color_scheme['secondary'])))
            story.append(Spacer(1, 0.1*inch))
        
        # Regular paragraph
        else:
            formatted_line = convert_markdown_formatting(line_stripped)
            story.append(Paragraph(formatted_line, custom_styles['body']))
        
        i += 1
    
    # Determine page size
    page_size = letter
    if single_page:
        # First estimate (fast) then fit to ensure 1 page and minimal whitespace
        measured_h = _calc_story_height(story, avail_width)
        buffer_h = 0.5 * inch
        initial_h = max(letter[1], measured_h + compact["top_margin"] + compact["bottom_margin"] + buffer_h)
        if not initial_h or initial_h <= 0:
            initial_h = _estimate_single_page_height(markdown_text, inline_images=inline_images)

        fitted_h = _fit_single_page_height(
            story,
            page_w=page_w,
            min_h=letter[1],
            initial_h=initial_h,
            max_h=500 * inch,
            topMargin=compact["top_margin"],
            bottomMargin=compact["bottom_margin"],
            leftMargin=compact["left_margin"],
            rightMargin=compact["right_margin"],
        )
        page_size = (page_w, fitted_h)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        topMargin=compact["top_margin"],
        bottomMargin=compact["bottom_margin"],
        leftMargin=compact["left_margin"],
        rightMargin=compact["right_margin"],
    )

    # Build PDF with custom canvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✓ Professional PDF created: {output_path}")
    return output_path


def create_pdf_from_markdown(
    markdown_text,
    title=None,
    base64_images=None,
    image_descriptions=None,
    max_pages: Optional[int] = None,
    single_page: bool = False,
):
    """
    Create a professional PDF report from markdown
    
    Args:
        markdown_text: Markdown formatted text
        title: Report title (optional)
        base64_images: List of base64 encoded images
        image_descriptions: List of image descriptions
    
    Returns:
        Base64 encoded PDF
    """
    charts_dir = Path.cwd() / "temp_charts"
    charts_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = charts_dir / f"vinvest_report_{timestamp}.pdf"
    
    # Prepare inline images
    inline_images = []
    try:
        if isinstance(base64_images, list):
            if base64_images and isinstance(base64_images[0], dict):
                inline_images = [{"image_base64": d.get("image_base64"), 
                                 "description": d.get("description","")} 
                                for d in base64_images]
            else:
                if isinstance(image_descriptions, list):
                    for b64, desc in zip(base64_images, image_descriptions):
                        inline_images.append({"image_base64": b64, "description": desc or ""})
                else:
                    inline_images = [{"image_base64": b64, "description": ""} 
                                    for b64 in base64_images]
    except Exception:
        inline_images = []
    
    try:
        output_path = markdown_to_pdf(
            markdown_text,
            output_path,
            title=title,
            inline_images=inline_images,
            single_page=single_page,
        )
    except LayoutError:
        # Robust fallback: if single-page fitting fails due to an unbreakable flowable,
        # retry in normal multi-page mode so API calls do not fail.
        output_path = markdown_to_pdf(
            markdown_text,
            output_path,
            title=title,
            inline_images=inline_images,
            single_page=False,
        )
    except Exception:
        # Same fallback policy for any other rendering error.
        output_path = markdown_to_pdf(
            markdown_text,
            output_path,
            title=title,
            inline_images=inline_images,
            single_page=False,
        )

    # Optionally trim pages (e.g., enforce cover+1-page output)
    if (not single_page) and (max_pages is not None):
        _trim_pdf_pages_inplace(Path(output_path), int(max_pages))
    
    # Convert to base64
    with open(output_path, 'rb') as pdf_file:
        pdf_content = pdf_file.read()
        base64_encoded = base64.b64encode(pdf_content).decode('utf-8')
    
    return base64_encoded
