"""
pdf_service.py — PDF generation for ClinIQ shift discharge summaries.

Uses reportlab (pure Python, no headless Chrome) to produce a formatted PDF
that a doctor can hand to the incoming team.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime
import json


# ── Colour palette ────────────────────────────────────────────────────────────
CLINIQ_TEAL   = colors.HexColor("#0891b2")
CLINIQ_DARK   = colors.HexColor("#0c1824")
CLINIQ_SURFACE = colors.HexColor("#122030")
RED_CRITICAL  = colors.HexColor("#ef4444")
AMBER_WARN    = colors.HexColor("#f59e0b")
GREEN_OK      = colors.HexColor("#10b981")
TEXT_MAIN     = colors.HexColor("#e2e8f0")
TEXT_MUTED    = colors.HexColor("#94a3b8")
WHITE         = colors.white


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=22,
            textColor=CLINIQ_TEAL, spaceAfter=2
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=10,
            textColor=TEXT_MUTED, spaceAfter=12
        ),
        "section": ParagraphStyle(
            "section", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=13,
            textColor=CLINIQ_TEAL, spaceBefore=14, spaceAfter=4
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9,
            textColor=colors.black, spaceAfter=4, leading=14
        ),
        "bold": ParagraphStyle(
            "bold", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=9,
            textColor=colors.black
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"],
            fontName="Helvetica", fontSize=8,
            textColor=colors.HexColor("#555555")
        ),
        "critical": ParagraphStyle(
            "critical", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=9,
            textColor=RED_CRITICAL
        ),
        "warning": ParagraphStyle(
            "warning", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=9,
            textColor=AMBER_WARN
        ),
        "letter_body": ParagraphStyle(
            "letter_body", parent=base["Normal"],
            fontName="Helvetica", fontSize=10,
            textColor=colors.black, spaceAfter=8, leading=16
        ),
    }


def _severity_color(sev: str) -> colors.Color:
    if sev == "critical":
        return RED_CRITICAL
    elif sev == "warning":
        return AMBER_WARN
    return GREEN_OK


def _flag_table(flags: list, styles: dict) -> Table | None:
    if not flags:
        return None
    data = [["Severity", "Title", "Detail", "Action"]]
    for f in flags:
        sev = f.get("severity", "watch")
        data.append([
            Paragraph(sev.upper(), styles["critical"] if sev == "critical" else
                      styles["warning"] if sev == "warning" else styles["small"]),
            Paragraph(str(f.get("title", "")), styles["bold"]),
            Paragraph(str(f.get("detail", f.get("explanation", f.get("description", "")))), styles["small"]),
            Paragraph(str(f.get("recommendation", f.get("action", ""))), styles["small"]),
        ])
    t = Table(data, colWidths=[22*mm, 40*mm, 70*mm, 45*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def generate_shift_pdf(
    shift: dict,
    analyses: list[dict],
    discharge_summary: dict | None = None,
    prescriptions: list[dict] | None = None,
) -> bytes:
    """
    Generate a full shift PDF report.
    
    Args:
        shift: ShiftSession dict (id, doctor_name, specialty, started_at, ended_at)
        analyses: List of Analysis dicts with output_data parsed
        discharge_summary: AI-generated discharge summary from groq_service
        prescriptions: List of Prescription dicts
    
    Returns:
        PDF bytes
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18*mm,
        rightMargin=18*mm,
        topMargin=18*mm,
        bottomMargin=18*mm,
    )
    styles = _styles()
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    started = shift.get("started_at", "")
    ended   = shift.get("ended_at", "")
    if hasattr(started, "strftime"):
        started = started.strftime("%d %b %Y %H:%M")
    if hasattr(ended, "strftime"):
        ended = ended.strftime("%d %b %Y %H:%M")

    story.append(Paragraph("ClinIQ — Shift Discharge Summary", styles["title"]))
    story.append(Paragraph(
        f"Dr {shift.get('doctor_name', 'Unknown')} · {shift.get('specialty', '')} · "
        f"{started} → {ended}",
        styles["subtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=CLINIQ_TEAL))
    story.append(Spacer(1, 6))

    # ── Statistics bar ────────────────────────────────────────────────────────
    by_type = {}
    for a in analyses:
        t = a.get("analysis_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    stat_data = [[
        Paragraph("SOAP Notes", styles["bold"]),
        Paragraph("Handovers", styles["bold"]),
        Paragraph("DDx", styles["bold"]),
        Paragraph("Rapid Notes", styles["bold"]),
        Paragraph("Prescriptions", styles["bold"]),
        Paragraph("Total", styles["bold"]),
    ], [
        Paragraph(str(by_type.get("soap", 0)), styles["section"]),
        Paragraph(str(by_type.get("handover", 0)), styles["section"]),
        Paragraph(str(by_type.get("differential_diagnosis", 0)), styles["section"]),
        Paragraph(str(by_type.get("rapid", 0)), styles["section"]),
        Paragraph(str(len(prescriptions) if prescriptions else 0), styles["section"]),
        Paragraph(str(len(analyses)), styles["section"]),
    ]]
    stat_tbl = Table(stat_data, colWidths=[28*mm]*6)
    stat_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f9ff")),
        ("GRID", (0, 0), (-1, -1), 0.3, CLINIQ_TEAL),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(stat_tbl)
    story.append(Spacer(1, 10))

    # ── AI Discharge Summary (GP letter) ─────────────────────────────────────
    if discharge_summary and not discharge_summary.get("error"):
        story.append(Paragraph("DISCHARGE / HANDOVER LETTER", styles["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=CLINIQ_TEAL))
        story.append(Spacer(1, 4))

        ds = discharge_summary
        story.append(Paragraph(ds.get("opening", "Dear Colleague,"), styles["letter_body"]))
        story.append(Paragraph(ds.get("shift_overview", ""), styles["letter_body"]))
        story.append(Spacer(1, 6))

        patients_seen = ds.get("patients_seen", [])
        for i, pt in enumerate(patients_seen, 1):
            pt_name = pt.get("name", f"Patient {i}")
            story.append(Paragraph(f"{i}. {pt_name}", styles["bold"]))

            pt_rows = [
                ["Presenting Complaint", pt.get("presenting_complaint", "—")],
                ["Assessment",          pt.get("assessment", "—")],
                ["Management",          pt.get("management", "—")],
                ["Diagnoses",           ", ".join(pt.get("diagnoses", [])) or "—"],
                ["Prescriptions",       pt.get("prescriptions", "—") or "None"],
                ["Disposition",         pt.get("disposition", "—")],
                ["Follow-up Required",  pt.get("follow_up", "—")],
            ]
            # Add ICD-10 if present
            icd = pt.get("icd10_codes", [])
            if icd:
                icd_str = ", ".join(f"{c['code']} ({c['description']})" for c in icd)
                pt_rows.append(["ICD-10 Codes", icd_str])
            # Safety flags
            sf = pt.get("safety_flags", [])
            if sf:
                pt_rows.append(["⚠ Safety Flags", " | ".join(sf)])

            pt_tbl = Table(
                [[Paragraph(r, styles["bold"]), Paragraph(v, styles["body"])] for r, v in pt_rows],
                colWidths=[38*mm, 132*mm]
            )
            pt_tbl.setStyle(TableStyle([
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(KeepTogether([pt_tbl, Spacer(1, 8)]))

        outstanding = ds.get("outstanding_tasks", [])
        if outstanding:
            story.append(Paragraph("Outstanding Tasks for Incoming Team", styles["section"]))
            for task in outstanding:
                story.append(Paragraph(f"• {task}", styles["body"]))

        critical_alerts = ds.get("critical_alerts", [])
        if critical_alerts:
            story.append(Spacer(1, 6))
            story.append(Paragraph("🚨 CRITICAL ALERTS", styles["critical"]))
            for alert in critical_alerts:
                story.append(Paragraph(f"▶ {alert}", styles["critical"]))

        story.append(Spacer(1, 8))
        story.append(Paragraph(ds.get("closing", "Yours sincerely,"), styles["letter_body"]))
        story.append(Spacer(1, 16))

    # ── SOAP Notes ────────────────────────────────────────────────────────────
    soap_analyses = [a for a in analyses if a.get("analysis_type") == "soap"]
    if soap_analyses:
        story.append(Paragraph("SOAP NOTES", styles["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=CLINIQ_TEAL))
        for idx, a in enumerate(soap_analyses, 1):
            d = a.get("output_data", {})
            ts = a.get("created_at", "")
            if hasattr(ts, "strftime"):
                ts = ts.strftime("%H:%M")

            news2 = d.get("news2", {})
            news2_score = news2.get("score", "—")
            news2_sev = news2.get("severity", "")
            qsofa = d.get("qsofa", {})

            # ICD-10 if available
            icd_data = d.get("icd10", {})
            icd_codes = icd_data.get("suggestions", []) if isinstance(icd_data, dict) else []

            story.append(Spacer(1, 6))
            story.append(Paragraph(f"Note {idx} — {ts}", styles["bold"]))

            soap_rows = [
                ["Subjective",  d.get("subjective", "—")],
                ["Objective",   d.get("objective", "—")],
                ["Assessment",  d.get("assessment", "—")],
                ["Plan",        d.get("plan", "—")],
                ["NEWS2 Score", f"{news2_score} ({news2_sev.upper()}) — {news2.get('action', '')}"],
                ["qSOFA",       f"{qsofa.get('score', '—')} — {qsofa.get('interpretation', '')}"],
            ]
            if icd_codes:
                icd_str = ", ".join(f"{c['code']} {c['description']}" for c in icd_codes[:3])
                soap_rows.append(["ICD-10", icd_str])

            soap_tbl = Table(
                [[Paragraph(r, styles["bold"]), Paragraph(str(v), styles["body"])] for r, v in soap_rows],
                colWidths=[28*mm, 142*mm]
            )
            soap_tbl.setStyle(TableStyle([
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(soap_tbl)

            # Red flags
            red_flags = d.get("red_flags", [])
            if red_flags:
                story.append(Spacer(1, 4))
                story.append(Paragraph("Red Flags:", styles["warning"]))
                ft = _flag_table(
                    [{"severity": f.get("severity"), "title": f.get("title"),
                      "detail": f.get("explanation"), "recommendation": ""} for f in red_flags],
                    styles
                )
                if ft:
                    story.append(ft)

    # ── DDx ───────────────────────────────────────────────────────────────────
    ddx_analyses = [a for a in analyses if a.get("analysis_type") == "differential_diagnosis"]
    if ddx_analyses:
        story.append(Spacer(1, 10))
        story.append(Paragraph("DIFFERENTIAL DIAGNOSES", styles["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=CLINIQ_TEAL))
        for a in ddx_analyses:
            d = a.get("output_data", {})
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"Presentation: {d.get('chief_complaint', '—')}", styles["bold"]))
            story.append(Paragraph(f"Most Likely: {d.get('most_likely', '—')}", styles["body"]))

            diffs = d.get("differentials", [])[:5]
            if diffs:
                diff_data = [["Rank", "Diagnosis", "Confidence", "Key Tests"]]
                for diff in diffs:
                    diff_data.append([
                        str(diff.get("rank", "")),
                        diff.get("diagnosis", ""),
                        f"{diff.get('confidence', '')}%",
                        ", ".join(diff.get("confirm_tests", [])[:2]),
                    ])
                dt = Table(diff_data, colWidths=[12*mm, 60*mm, 22*mm, 76*mm])
                dt.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(dt)

            # Top ICD-10 for DDx
            icd = d.get("top_icd10", [])
            if icd:
                icd_str = "  |  ".join(f"{c['code']} — {c['description']} ({c.get('confidence','?')}%)" for c in icd[:3])
                story.append(Paragraph(f"ICD-10: {icd_str}", styles["small"]))

    # ── Prescription Safety ───────────────────────────────────────────────────
    if prescriptions:
        story.append(Spacer(1, 10))
        story.append(Paragraph("PRESCRIPTIONS & SAFETY CHECKS", styles["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=CLINIQ_TEAL))
        for rx in prescriptions:
            ts = rx.get("created_at", "")
            if hasattr(ts, "strftime"):
                ts = ts.strftime("%H:%M")

            drugs = rx.get("drugs", [])
            safety = rx.get("safety_result", {})
            overall = safety.get("overall_safety", "unknown")
            flags = safety.get("flags", [])
            critical_flags = [f for f in flags if f.get("severity") == "critical"]

            sev_style = styles["critical"] if overall == "dangerous" else (
                styles["warning"] if overall == "caution" else styles["body"])

            story.append(Spacer(1, 6))
            story.append(Paragraph(f"Prescription at {ts} — Status: {overall.upper()}", sev_style))
            story.append(Paragraph(f"Drugs: {', '.join(drugs)}", styles["body"]))

            if flags:
                ft = _flag_table(flags, styles)
                if ft:
                    story.append(ft)

            adj = safety.get("dose_adjustments", [])
            if adj:
                story.append(Paragraph("Dose Adjustments:", styles["warning"]))
                for a in adj:
                    story.append(Paragraph(
                        f"• {a['drug']}: {a.get('current','?')} → {a.get('recommended','?')} ({a.get('reason','')})",
                        styles["small"]
                    ))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TEXT_MUTED))
    story.append(Spacer(1, 4))
    generated_at = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")
    story.append(Paragraph(
        f"Generated by ClinIQ AI Clinical Assistant · {generated_at} · "
        f"Shift #{shift.get('id', '—')} · For clinical use only — verify all AI output",
        styles["small"]
    ))

    doc.build(story)
    return buf.getvalue()
