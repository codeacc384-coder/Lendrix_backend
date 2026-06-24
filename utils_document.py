import os
import uuid
import boto3
from io import BytesIO
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

load_dotenv()

_s3_client = None


def get_s3_client():
    """Return a module-level singleton S3 client to avoid creating a new connection on every call."""
    global _s3_client
    if _s3_client is None:
        endpoint = os.getenv("UTHO_ENDPOINT_URL", "").rstrip("/")
        _s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.getenv("UTHO_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("UTHO_SECRET_KEY"),
            config=boto3.session.Config(signature_version="s3v4")
        )
    return _s3_client


# Keep _get_s3 as an alias so existing internal calls still work
_get_s3 = get_s3_client


def generate_and_upload_policy_pdf(name: str, category: str, description: str, limitations: list[dict], existing_key: str = None) -> tuple[str, str]:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#1a1a2e"), spaceAfter=6)
    heading_style = ParagraphStyle("heading", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#16213e"), spaceBefore=12, spaceAfter=4)
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14, textColor=colors.HexColor("#333333"))
    label_style = ParagraphStyle("label", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#666666"), spaceBefore=2)

    elements = []
    elements.append(Paragraph("Lendrix Ventech", ParagraphStyle("brand", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#888888"))))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph(name, title_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a1a2e")))
    elements.append(Spacer(1, 0.4*cm))

    meta_table = Table([["Category", category or "—"]], colWidths=[3*cm, 14*cm])
    meta_table.setStyle(TableStyle([("FONTSIZE", (0,0), (-1,-1), 9), ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#666666")), ("TEXTCOLOR", (1,0), (1,-1), colors.HexColor("#333333")), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    elements.append(meta_table)
    elements.append(Spacer(1, 0.4*cm))

    if description:
        elements.append(Paragraph("Description", heading_style))
        elements.append(Paragraph(description, body_style))
        elements.append(Spacer(1, 0.4*cm))

    if limitations:
        elements.append(Paragraph("Limitations", heading_style))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
        elements.append(Spacer(1, 0.2*cm))
        for i, lim in enumerate(limitations, 1):
            elements.append(Paragraph(f"{i}. {lim.get('title', '')}", ParagraphStyle("lim_title", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#1a1a2e"))))
            if lim.get("description"):
                elements.append(Paragraph(lim["description"], body_style))
            elements.append(Paragraph(f"Status: {'Enabled' if lim.get('is_enabled', True) else 'Disabled'}", label_style))
            elements.append(Spacer(1, 0.3*cm))

    doc.build(elements)
    buffer.seek(0)

    bucket = os.getenv("BUCKET_NAME", "documents")
    object_key = existing_key if existing_key else f"policies/{uuid.uuid4()}_{name.replace(' ', '_')}.pdf"
    try:
        s3 = _get_s3()
        s3.upload_fileobj(buffer, bucket, object_key, ExtraArgs={"ContentType": "application/pdf", "ContentDisposition": "inline"})
    except Exception as e:
        raise RuntimeError(f"Failed to upload policy document: {e}")
    document_url = f"{os.getenv('UTHO_ENDPOINT_URL', '').rstrip('/')}/{bucket}/{object_key}"
    return document_url, object_key
