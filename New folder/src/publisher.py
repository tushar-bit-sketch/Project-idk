import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from .models import ShiftHandoverReport

def publish_to_pdf(report: ShiftHandoverReport, output_path: str):
    try:
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(out_file),
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=6
        )

        meta_style = ParagraphStyle(
            "MetaStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#4A5568")
        )

        summary_box_style = ParagraphStyle(
            "SummaryBox",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#2D3748")
        )

        section_heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=10,
            spaceAfter=4
        )

        item_text_style = ParagraphStyle(
            "ItemText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1A202C")
        )

        source_tag_style = ParagraphStyle(
            "SourceTag",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#718096")
        )

        empty_section_style = ParagraphStyle(
            "EmptySection",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#A0AEC0")
        )

        story = []

        story.append(Paragraph("Operational Shift Handover Report", title_style))
        story.append(Paragraph(f"<b>Shift Window:</b> {report.shift_start} &mdash; {report.shift_end} ({report.timezone})", meta_style))
        story.append(Paragraph(f"<b>Generated At:</b> {report.generated_at} | <b>Shift ID:</b> {report.shift_id}", meta_style))
        if report.unreachable_sources:
            unr = ", ".join(report.unreachable_sources)
            story.append(Paragraph(f"<font color='#E53E3E'><b>Notice:</b> Skipped unreachable/degraded sources: {unr}</font>", meta_style))
        
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#CBD5E0"), spaceAfter=8))

        story.append(Paragraph(f"<b>Executive Shift Summary:</b> {report.summary_paragraph}", summary_box_style))
        story.append(Spacer(1, 8))

        sections = [
            ("1. Completed Work", report.completed, colors.HexColor("#22543D")),
            ("2. In Progress", report.in_progress, colors.HexColor("#2B6CB0")),
            ("3. Blockers / Escalations", report.blockers, colors.HexColor("#9B2C2C")),
            ("4. Watch-list", report.watch_list, colors.HexColor("#744210")),
        ]

        for heading, items, color_accent in sections:
            story.append(Paragraph(f"<font color='{color_accent.hexval()}'>{heading}</font>", section_heading_style))
            story.append(HRFlowable(width="100%", thickness=0.75, color=color_accent, spaceAfter=4))
            
            if not items:
                story.append(Paragraph("&bull; Nothing to report", empty_section_style))
                story.append(Spacer(1, 4))
            else:
                table_data = []
                for itm in items:
                    p_content = Paragraph(f"&bull; {itm.item}", item_text_style)
                    p_src = Paragraph(f"Source: {itm.source}<br/>{itm.timestamp}", source_tag_style)
                    table_data.append([p_content, p_src])

                col_widths = [doc.width * 0.72, doc.width * 0.28]
                t = Table(table_data, colWidths=col_widths)
                t.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
                ]))
                story.append(t)
                story.append(Spacer(1, 4))

        doc.build(story)
        print(f"Successfully published handover document to: {out_file}")
    except Exception as e:
        print(f"FATAL: Document export failed: {e}", file=sys.stderr)
        sys.exit(1)

def publish_to_slack_format(report: ShiftHandoverReport, output_path: str):
    lines = []
    lines.append(f"*:clipboard: Operational Shift Handover Note ({report.shift_id})*")
    lines.append(f"*Window:* `{report.shift_start}` to `{report.shift_end}` ({report.timezone})")
    lines.append(f"*Summary:* {report.summary_paragraph}\n")

    def format_sec(title, items):
        lines.append(f"*{title}*")
        if not items:
            lines.append("> _Nothing to report_")
        else:
            for itm in items:
                lines.append(f"> - {itm.item} `[{itm.source}]`")
        lines.append("")

    format_sec("Completed Work", report.completed)
    format_sec("In Progress", report.in_progress)
    format_sec("Blockers / Escalations", report.blockers)
    format_sec("Watch-list", report.watch_list)

    text_content = "\n".join(lines)
    Path(output_path).resolve().write_text(text_content, encoding="utf-8")
    return text_content
