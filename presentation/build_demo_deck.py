"""Build the ShelfSense demo deck and the flowchart PNG."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

OUT = Path(__file__).resolve().parent
PNG = OUT / "shelfsense-flow.png"
PPTX = OUT / "ShelfSense_Demo.pptx"

NAVY = (7, 17, 31)
CARD = (18, 32, 54)
WHITE = (244, 247, 251)
MUTED = (154, 168, 195)
BLUE = (122, 162, 255)
GREEN = (62, 224, 162)
AMBER = (255, 176, 32)
ROSE = (255, 93, 115)
LINE = (48, 64, 92)

FONT = "C:/Windows/Fonts/segoeui.ttf"
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def wrap(draw, text, face, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = word if not cur else f"{cur} {word}"
        if draw.textlength(trial, font=face) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def rounded(draw, box, fill, outline=None, radius=22, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_block(draw, box, lines, face, fill, align="center", gap=6):
    x0, y0, x1, y1 = box
    heights = [draw.textbbox((0, 0), line, font=face)[3] for line in lines]
    total = sum(heights) + gap * (len(lines) - 1)
    y = y0 + (y1 - y0 - total) / 2
    for line, h in zip(lines, heights):
        w = draw.textlength(line, font=face)
        x = x0 + 28 if align == "left" else x0 + (x1 - x0 - w) / 2
        draw.text((x, y), line, font=face, fill=fill)
        y += h + gap


def arrow(draw, points, fill=BLUE):
    draw.line(points, fill=fill, width=5)
    x2, y2 = points[-1]
    x1, y1 = points[-2]
    if abs(x2 - x1) >= abs(y2 - y1):
        sign = 1 if x2 > x1 else -1
        head = [(x2, y2), (x2 - 16 * sign, y2 - 9), (x2 - 16 * sign, y2 + 9)]
    else:
        sign = 1 if y2 > y1 else -1
        head = [(x2, y2), (x2 - 9, y2 - 16 * sign), (x2 + 9, y2 - 16 * sign)]
    draw.polygon(head, fill=fill)


def build_flow():
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), NAVY)
    draw = ImageDraw.Draw(img)
    title = font(40, True)
    sub = font(22)
    small = font(18)
    body = font(24, True)
    draw.text((64, 36), "ShelfSense", font=title, fill=WHITE)
    draw.text((64, 90), "On-prem store server price compliance using an edge AI model", font=sub, fill=WHITE)
    draw.text(
        (64, 126),
        "llama3.2:3b  ·  Meta Llama 3.2, 3 billion parameters  ·  local Ollama on the store GPU",
        font=small,
        fill=BLUE,
    )

    lanes = [
        (48, 180, 900, 980, BLUE, "PHONE"),
        (1020, 180, 1872, 980, GREEN, "ON-PREM STORE SERVER"),
    ]
    for x0, y0, x1, y1, color, label in lanes:
        rounded(draw, (x0, y0, x1, y1), (12, 22, 40), color, radius=28, width=2)
        draw.text((x0 + 28, y0 + 18), label, font=font(18, True), fill=color)

    steps = [
        (76, 240, 872, 390, "1", "Point the camera at the shelf label", BLUE),
        (76, 420, 872, 570, "2", "Read the barcode and the printed price on the device", BLUE),
        (76, 600, 872, 750, "3", "Save the scan on the phone. It waits if the network is down", BLUE),
        (76, 780, 872, 940, "4", "Send only the barcode, the price, and the confidence", BLUE),
        (1048, 240, 1844, 390, "5", "Compare those numbers with the store price list", GREEN),
        (1048, 420, 1844, 590, "6", "Match, mismatch, unknown item, or rescan", GREEN),
        (1048, 620, 1844, 790, "7", "llama3.2:3b writes the task from the store SOP", GREEN),
        (1048, 820, 1844, 960, "8", "Close it: label replaced, or OCR misread for the model team", AMBER),
    ]
    for x0, y0, x1, y1, num, label, color in steps:
        rounded(draw, (x0, y0, x1, y1), CARD, color, radius=20, width=3)
        draw.ellipse((x0 + 22, y0 + 48, x0 + 74, y0 + 100), fill=color)
        nw = draw.textlength(num, font=font(26, True))
        draw.text((x0 + 48 - nw / 2, y0 + 58), num, font=font(26, True), fill=NAVY)
        lines = wrap(draw, label, body, x1 - x0 - 120)
        text_block(draw, (x0 + 84, y0, x1 - 16, y1), lines, body, WHITE, align="left")

    for y in (390, 570, 750):
        arrow(draw, [(474, y + 6), (474, y + 24)], BLUE)
    for y in (390, 590, 790):
        arrow(draw, [(1446, y + 6), (1446, y + 24)], GREEN)

    arrow(draw, [(872, 860), (948, 860), (948, 315), (1048, 315)], GREEN)
    draw.text((960, 560), "to the", font=small, fill=MUTED)
    draw.text((956, 584), "server", font=small, fill=MUTED)
    img.save(PNG)
    return PNG


def rgb(c):
    return RGBColor(*c)


def set_run(paragraph, text, size, bold=False, color=WHITE, align=None):
    paragraph.clear()
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    run.font.name = "Segoe UI"
    if align:
        paragraph.alignment = align
    return run


def add_bg(slide, prs):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(NAVY)
    shape.line.fill.background()
    return shape


def add_box(slide, l, t, w, h, text, size=28, bold=False, color=WHITE, fill=None, align=PP_ALIGN.LEFT):
    shape = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(fill)
    frame = shape.text_frame
    frame.word_wrap = True
    frame.auto_size = None
    frame.margin_left = Emu(0)
    frame.margin_right = Emu(0)
    frame.margin_top = Emu(0)
    set_run(frame.paragraphs[0], text, size, bold, color, align)
    return frame


def add_bullets(slide, l, t, w, h, items, size=26):
    shape = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.word_wrap = True
    for i, item in enumerate(items):
        p = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        p.level = 0
        p.space_after = Pt(14)
        set_run(p, item, size, False, WHITE)
    return frame


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def build_deck():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    s = prs.slides.add_slide(blank)
    add_bg(s, prs)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), prs.slide_height)
    bar.fill.solid()
    bar.fill.fore_color.rgb = rgb(GREEN)
    bar.line.fill.background()
    add_box(s, 0.7, 1.5, 12, 0.5, "SHELFSENSE", 20, True, GREEN)
    add_box(s, 0.7, 2.1, 12, 1.4, "On-prem store server\nprice compliance", 48, True)
    add_box(s, 0.7, 4.5, 12, 0.6, "Using an edge AI model", 32, True, BLUE)
    add_box(
        s,
        0.7,
        5.4,
        12,
        1.2,
        "llama3.2:3b\nMeta Llama 3.2  ·  3 billion parameters  ·  about 2 GB\nLocal Ollama on the store GPU. The photo and the model stay in the store.",
        20,
        False,
        MUTED,
    )
    notes(s, "Open with the one-sentence purpose: catch a wrong shelf price before a customer does, on hardware that stays in the store.")

    s = prs.slides.add_slide(blank)
    add_bg(s, prs)
    add_box(s, 0.6, 0.4, 12, 0.8, "What this achieves", 40, True)
    add_bullets(
        s,
        0.7,
        1.6,
        12,
        5,
        [
            "An associate points a phone at a shelf label.",
            "The phone reads the barcode and the printed price. The photo stays on the device.",
            "The laptop, acting as the store server, checks those numbers against the price list.",
            "A wrong label becomes a short task, with a one-hour or four-hour deadline from the store SOP.",
            "If the network or the model is down, the scan is kept and the task is still written.",
        ],
        26,
    )
    notes(s, "Bigger picture before any architecture. Compliance and revenue: a shelf price lower than the system may have to be honored at checkout.")

    s = prs.slides.add_slide(blank)
    add_bg(s, prs)
    s.shapes.add_picture(str(PNG), Inches(0.15), Inches(0.05), Inches(13.03), Inches(7.35))
    notes(s, "Walk the eight steps. Stress step 4: only barcode, price, and confidence cross the network. Step 7 is llama3.2:3b. If Ollama is stopped, the source flips to rules.")

    s = prs.slides.add_slide(blank)
    add_bg(s, prs)
    add_box(s, 0.6, 0.4, 12, 0.7, "Phone side", 40, True, BLUE)
    add_bullets(
        s,
        0.7,
        1.5,
        12,
        5.2,
        [
            "Camera looks at the label. Barcode and price are read on the device.",
            "The associate taps Capture. The scan is stored on the phone with its own id.",
            "Airplane mode does not lose the scan. Sync now sends it when Wi-Fi returns.",
            "A retry is safe. The server ignores a scan it has already stored.",
            "On a rugged handheld, the hardware scanner can fill the barcode. A regular phone uses the camera for both.",
        ],
        26,
    )
    notes(s, "The demo phone is any Android device with a camera. Point shelfsense.baseUrl at the laptop Wi-Fi address, with a trailing slash.")

    s = prs.slides.add_slide(blank)
    add_bg(s, prs)
    add_box(s, 0.6, 0.35, 12, 1.3, "On-prem store server\nprice compliance using an edge AI model", 34, True)
    add_bullets(
        s,
        0.7,
        2.3,
        12,
        4.6,
        [
            "This laptop is the store server. Dashboard: http://127.0.0.1:8000",
            "Price check is a rule against the price list, not a guess by the model.",
            "Edge model: llama3.2:3b, Meta Llama 3.2, 3 billion parameters, about 2 GB.",
            "It runs locally with Ollama on the store GPU and writes the associate task.",
            "Stop Ollama and the same task is written from fixed rules. Source changes from llm:llama3.2:3b to rules.",
        ],
        24,
    )
    notes(s, "API key for the dashboard is the SHELFSENSE_API_KEY you started the server with. llama3.2:3b is pulled with Ollama and is not stored in this repo.")

    s = prs.slides.add_slide(blank)
    add_bg(s, prs)
    add_box(s, 0.6, 0.4, 12, 0.7, "How a scan is decided", 40, True)
    add_bullets(
        s,
        0.7,
        1.45,
        12,
        5.4,
        [
            "Match. Shelf price and system price are the same. An open issue for that item closes.",
            "Mismatch. Prices differ. Shelf lower than system: fix within 1 hour. Shelf higher: fix within 4 hours.",
            "Unknown item. The barcode is not in the price list. Set it aside.",
            "Rescan. The price was missing, or confidence was under 0.60.",
            "Close a mismatch as Label replaced, or as OCR misread. A misread is kept as a labeled example.",
        ],
        24,
    )
    notes(s, "Demo labels: Cola 12pk at $6.99 is a match. AA Batteries label is $9.99 versus system $10.99, the 1-hour case. Tissue Box label is $3.99 versus system $3.49, the 4-hour case. Read the price columns before reading the model sentence.")

    s = prs.slides.add_slide(blank)
    add_bg(s, prs)
    add_box(s, 0.6, 0.4, 12, 0.7, "Five-minute demo", 40, True)
    add_bullets(
        s,
        0.7,
        1.4,
        12,
        5.5,
        [
            "1. Dashboard is empty. This laptop is the store server.",
            "2. Scan Cola at $6.99. Match. Only two numbers crossed the network.",
            "3. Scan AA Batteries, label $9.99, system $10.99. Mismatch, 1-hour task, source llm:llama3.2:3b.",
            "4. Airplane mode, scan two labels, then Sync now.",
            "5. Stop Ollama and scan again. Source becomes rules. Then mark one row as an OCR misread.",
        ],
        24,
    )
    notes(s, "Labels file: D:\\AI\\projects\\shelfsense\\server\\labels.html. Backup with no phone: python simulate_scans.py --server http://127.0.0.1:8000 from the server folder, with SHELFSENSE_API_KEY set.")

    prs.save(PPTX)
    return PPTX


if __name__ == "__main__":
    build_flow()
    build_deck()
    print(PNG)
    print(PPTX)
