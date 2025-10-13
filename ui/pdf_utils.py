from pathlib import Path

from reportlab.pdfgen import canvas


def generate_paystub_pdf(filename: Path, lines: list, receipt_size=(216, 400)):
    """Create a simple PDF from a list of (align, text) tuples.

    align is 'center' or 'left'. filename is a Path instance.
    """
    c = canvas.Canvas(str(filename), pagesize=receipt_size)
    c.setFont('Helvetica', 10)
    y = receipt_size[1] - 20
    for align, text in lines:
        if align == 'center':
            c.drawCentredString(receipt_size[0] // 2, y, text)
        else:
            c.drawString(10, y, text)
        y -= 20
    c.save()
