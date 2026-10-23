"""Synthetic reference-content fixtures, NOT the employer's manuals."""

import fitz


def make_pdf(version=1, removed=False):
    doc = fitz.open()
    page = doc.new_page()
    y = 60

    def line(text, heading=False):
        nonlocal page, y
        if y > 735:
            page = doc.new_page()
            y = 60
        page.insert_text(
            (50, y),
            text,
            fontname="hebo" if heading else "helv",
            fontsize=12 if heading else 10,
        )
        y += 22

    def section(number, title, body=None):
        line(f"{number} {title}", True)
        if body:
            line(body)

    def table(rows):
        nonlocal y
        if y + len(rows) * 40 > 735:
            nonlocal page
            page = doc.new_page()
            y = 60
        x = [50, 160, 450]
        start = y
        for row in rows:
            for i, cell in enumerate(row):
                page.insert_textbox(
                    fitz.Rect(x[i] + 5, y + 3, x[i + 1] - 5, y + 37), cell, fontsize=9
                )
            y += 40
        for xx in x:
            page.draw_line((xx, start), (xx, y))
        for yy in range(int(start), int(y) + 1, 40):
            page.draw_line((x[0], yy), (x[-1], yy))
        y += 20

    line("CardioTrack CT-200", True)
    line("Synthetic Reference Manual", True)
    section("1", "Introduction", "Use only in controlled bench verification.")
    section("2", "Specifications")
    section("2.1", "Technical Specifications")
    table([["Parameter", "Specification"], ["Pressure", "299 mmHg maximum"]])
    section(
        "2.1.1.1",
        "Battery Life Under Typical Use",
        f"Approximately {300 if version == 1 else 250} measurement cycles. Low battery below {15 if version == 1 else 10}%.",
    )
    section("3", "Operation")
    section(
        "3.2", "Inflation", f"Inflate in {40 if version == 1 else 30} mmHg increments."
    )
    section("3.4", "Auto Shutoff", "Auto shutoff after 3 minutes.")
    section(
        "3.3", "Result Display and Classification", "Refer to Sections 2.1 and 4.3."
    )
    for i, title in enumerate(
        [
            "Normal",
            "Elevated",
            "Hypertension Stage 1",
            "Hypertension Stage 2",
            "Hypertensive Crisis",
        ],
        1,
    ):
        line(f"{i}. {title}")
    line("60 seconds is the observation interval.")
    line("1.5 seconds is not a section heading.")
    section("4", "Safety")
    section(
        "4.1",
        "Emergency Venting",
        "Pressure above 299 mmHg triggers venting within 2 seconds.",
    )
    section("4.2", "Error Codes")
    rows = [
        ["Code", "Behavior"],
        ["E1", "Sensor failure"],
        ["E2", "Movement detected"],
        [
            "E3",
            f"Deflates within {2 if version == 1 else 1.5} seconds\nunder controlled pressure",
        ],
        ["E4", "Low battery"],
        ["E5", "Internal failure"],
    ]
    if version == 2:
        rows.append(["E6", "Export error"])
    table(rows)
    section(
        "4.3",
        "Alarm Thresholds",
        f"Handle E1-E{5 if version == 1 else 6} as specified.",
    )
    section("5", "Data")
    if version == 2:
        section("5.3", "Data Export", "Export readings using the documented interface.")
    section("7", "Troubleshooting")
    section("7.1", "Error Codes", "Refer to service support for recurring errors.")
    if not removed:
        section("8", "Classification")
        section("8.1", "Classification", "Class II.")
    raw = doc.tobytes()
    doc.close()
    return raw
