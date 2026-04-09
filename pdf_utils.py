from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

def generate_pdf(content, filename="output.pdf"):
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    story = [Paragraph(line, styles["Normal"]) for line in content.split("\n")]
    doc.build(story)
    return filename