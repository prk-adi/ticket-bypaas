from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from flask import Flask, Response, render_template, request
from pypdf import PdfReader, PdfWriter
from pypdf._page import PageObject
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

APP_DIR = Path(__file__).resolve().parent
TEMPLATE_PDF = APP_DIR.parent / "ASIPAYGOV_q_eLEmF8PoD7fGHW5qv6UKyrVN7FdgJUwz.pdf"
MAX_ADULTS = 5
MAX_CHILDREN = 3
TZ = timezone(timedelta(hours=5, minutes=30), name="IST")

app = Flask(__name__)


def _now_india() -> datetime:
    return datetime.now(TZ)


def _ticket_type_label(adult_count: int, child_count: int) -> str:
    return f"Adult ({adult_count} Adults,{child_count} Children)"


def _validate_visitors_payload(visitor_count: int) -> list[dict[str, str]]:
    visitors: list[dict[str, str]] = []
    for i in range(1, visitor_count + 1):
        name = request.form.get(f"visitor_name_{i}", "").strip()
        age = request.form.get(f"age_{i}", "").strip()
        gender = request.form.get(f"gender_{i}", "").strip()
        if not name:
            raise ValueError(f"Visitor Name is required for Visitor {i}.")
        if not age.isdigit() or not (1 <= int(age) <= 120):
            raise ValueError(f"Age must be a valid number (1-120) for Visitor {i}.")
        if gender not in {"Male", "Female", "Other"}:
            raise ValueError(f"Gender is required for Visitor {i}.")
        age_int = int(age)
        visitor_type = "CHILD" if age_int < 15 else "ADULT"
        asi_fee = "Rs. 0" if visitor_type == "CHILD" else "Rs. 35"
        visitors.append(
            {
                "name": name,
                "age": age,
                "gender": gender,
                "visitor_type": visitor_type,
                "asi_fee": asi_fee,
            }
        )
    return visitors


def _draw_overlay(values: dict[str, str]) -> BytesIO:
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    page_w, page_h = letter

    # White patches to hide existing values while keeping original layout.
    patches = [
        (99, page_h - 168, 175, 14),   # Visitor Name
        (99, page_h - 200, 166, 14),   # Ticket Type value only
        (99, page_h - 232, 42, 14),    # Age
        (347, page_h - 200, 32, 14),   # ASI Fee (Rs. 35 / Rs. 0)
        (345, page_h - 328, 70, 14),   # Gender
        (84, page_h - 368, 200, 14),   # Booked at value only
        (73, page_h - 396, 78, 12),    # Date value only (avoid horizontal line below)
    ]

    can.setFillColorRGB(1, 1, 1)
    for x, y, w, h in patches:
        can.rect(x, y, w, h, fill=1, stroke=0)

    can.setFillColorRGB(0, 0, 0)
    can.setFont("Times-Roman", 10)
    can.drawString(100, page_h - 163, values["visitor_name"])
    can.drawString(100, page_h - 195, values["ticket_type"])
    can.drawString(100, page_h - 227, values["age"])
    can.drawString(347, page_h - 195, values["asi_fee"])
    can.drawString(347, page_h - 322, values["gender"])
    can.drawString(84, page_h - 364, values["booked_at"])
    can.drawString(73, page_h - 392, values["date"])

    can.save()
    packet.seek(0)
    return packet


def build_ticket_pdf(
    adult_count: int, child_count: int, visitors: list[dict[str, str]]
) -> bytes:
    reader = PdfReader(str(TEMPLATE_PDF))
    writer = PdfWriter()
    now = _now_india()
    ticket_type = _ticket_type_label(adult_count, child_count)
    booked_at = now.strftime("%a, %d %b %Y %H:%M:%S IST")
    current_date = now.strftime("%d/%m/%Y")
    template_page = reader.pages[0]

    for i in range(len(visitors)):
        page = PageObject.create_blank_page(
            width=float(template_page.mediabox.width),
            height=float(template_page.mediabox.height),
        )
        page.merge_page(template_page)
        overlay_data = {
            "visitor_name": visitors[i]["name"],
            "ticket_type": ticket_type,
            "age": visitors[i]["age"],
            "gender": visitors[i]["gender"],
            "asi_fee": visitors[i]["asi_fee"],
            "booked_at": booked_at,
            "date": current_date,
        }
        overlay_pdf = PdfReader(_draw_overlay(overlay_data))
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@app.get("/")
def index() -> str:
    return render_template(
        "index.html",
        max_adults=MAX_ADULTS,
        max_children=MAX_CHILDREN,
        max_total=MAX_ADULTS + MAX_CHILDREN,
    )


@app.post("/generate")
def generate() -> Response:
    try:
        adult_count = int(request.form.get("adult_count", "0"))
        child_count = int(request.form.get("child_count", "0"))
    except ValueError:
        adult_count = 0
        child_count = 0
    visitor_count = adult_count + child_count

    if not TEMPLATE_PDF.exists():
        return Response(f"Template PDF not found at: {TEMPLATE_PDF}", status=500)
    if adult_count < 0 or adult_count > MAX_ADULTS:
        return Response("Adults must be between 0 and 5.", status=400)
    if child_count < 0 or child_count > MAX_CHILDREN:
        return Response("Children must be between 0 and 3.", status=400)
    if visitor_count < 1:
        return Response("At least one visitor is required.", status=400)

    try:
        visitors = _validate_visitors_payload(visitor_count)
    except ValueError as exc:
        return Response(str(exc), status=400)

    derived_adults = sum(1 for v in visitors if v["visitor_type"] == "ADULT")
    derived_children = len(visitors) - derived_adults
    if derived_adults > MAX_ADULTS:
        return Response("Adult visitors by age cannot exceed 5.", status=400)
    if derived_children > MAX_CHILDREN:
        return Response("Child visitors by age cannot exceed 3.", status=400)

    pdf_bytes = build_ticket_pdf(derived_adults, derived_children, visitors)
    file_name = f"generated_ticket_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
