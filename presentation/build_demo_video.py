"""Turn the recorded dashboard frames into a GIF and an MP4."""
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SHOTS = Path(r"C:\Users\zkhan\AppData\Local\Temp\cursor\screenshots")
NAVY = (7, 17, 31)
WHITE = (244, 247, 251)
MUTED = (186, 198, 214)
BLUE = (122, 162, 255)
GREEN = (62, 224, 162)
AMBER = (255, 176, 32)
W, H = 1280, 800
FONT = "C:/Windows/Fonts/segoeui.ttf"
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"


def face(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def wrap(draw, text, f, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = word if not cur else f"{cur} {word}"
        if draw.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def card(title, lines, accent=GREEN):
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 10, H), fill=accent)
    draw.text((64, 150), title, font=face(54, True), fill=WHITE)
    y = 250
    body = face(30)
    for line in lines:
        for wrapped in wrap(draw, line, body, W - 140):
            draw.text((64, y), wrapped, font=body, fill=MUTED)
            y += 46
        y += 18
    return img


def stage_phone(phone, title, lines, accent=GREEN):
    canvas = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(canvas)
    target_h = H - 40
    target_w = max(1, int(phone.width * target_h / phone.height))
    shot = phone.resize((target_w, target_h), Image.Resampling.LANCZOS)
    canvas.paste(shot, (20, 20))
    x = 20 + target_w + 36
    draw.rectangle((x - 18, 0, x - 8, H), fill=accent)
    draw.text((x, 70), title, font=face(34, True), fill=WHITE)
    y = 140
    body = face(24)
    for line in lines:
        for wrapped in wrap(draw, line, body, W - x - 36):
            draw.text((x, y), wrapped, font=body, fill=MUTED)
            y += 36
        y += 14
    return canvas


def fit_dashboard(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    last = 0
    for y in range(int(h * 0.75)):
        bright = False
        for x in range(0, w, 6):
            r, g, b = px[x, y]
            if r + g + b > 200:
                bright = True
                break
        if bright:
            last = y
    cropped = img.crop((0, 0, min(w, 1280), min(h, last + 28)))
    canvas = Image.new("RGB", (W, H), NAVY)
    fitted = cropped.resize((W, H), Image.Resampling.LANCZOS)
    canvas.paste(fitted, (0, 0))
    return canvas


def grab_phone(ffmpeg, t):
    out = ROOT / "_frames" / f"phone-{int(t * 10):03d}.png"
    import subprocess
    subprocess.check_call(
        [ffmpeg, "-y", "-ss", str(t), "-i", str(Path(r"C:\Users\zkhan\AppData\Local\Temp\shelfsense-live.mp4")), "-frames:v", "1", str(out)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return Image.open(out).convert("RGB")


def main():
    import imageio_ffmpeg as ffmpeg_mod
    ffmpeg = ffmpeg_mod.get_ffmpeg_exe()
    (ROOT / "_frames").mkdir(exist_ok=True)
    reading = grab_phone(ffmpeg, 3)
    result = grab_phone(ffmpeg, 16)
    dashboard = fit_dashboard(SHOTS / "phone-demo-dashboard.png")
    frames = [
        (card("ShelfSense on a Pixel", [
            "The phone reads the shelf label. The store server decides.",
            "Nothing to install. This is the real app.",
        ]), 3.5),
        (stage_phone(reading, "The phone reads it", [
            "Barcode 070847811169, shelf price $4.59, OCR confidence 50%.",
            "The photo never leaves the device.",
            "Recent scans already show a match and a price mismatch.",
        ], BLUE), 6.0),
        (card("Capture", [
            "One tap sends the barcode, the price, and the confidence.",
            "The store server compares the price with its list. The model does not make that call.",
        ], AMBER), 4.5),
        (stage_phone(result, "Three results on the phone", [
            "This read was 50% confident, under the 60% line, so the server asked for a rescan.",
            "Energy Drink at $2.99 matched.",
            "Cola at $4.59 against $6.99 is a price mismatch.",
        ], AMBER), 6.5),
        (card("Same scan, store server", [
            "The Pixel's read landed as Needs recapture for Energy Drink 16oz.",
            "Shelf $4.59, system $2.99, confidence 0.50. The task came from the fixed rule.",
        ], GREEN), 4.5),
        (dashboard, 6.5),
    ]

    stills = ROOT / "_frames"
    stills.mkdir(exist_ok=True)
    gif_frames = []
    durations = []
    for i, (img, seconds) in enumerate(frames):
        img.save(stills / f"{i:02d}.png")
        small = img.resize((960, 600), Image.Resampling.LANCZOS)
        gif_frames.append(small.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
        durations.append(int(seconds * 1000))
    gif_path = ROOT / "demo.gif"
    gif_frames[0].save(
        gif_path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    mp4_path = ROOT / "demo.mp4"
    import subprocess
    # One still per scene. The concat file holds each frame for its duration.
    concat = stills / "list.txt"
    lines = []
    for i, (_, seconds) in enumerate(frames):
        lines.append(f"file '{(stills / f'{i:02d}.png').as_posix()}'")
        lines.append(f"duration {seconds}")
    lines.append(f"file '{(stills / f'{len(frames)-1:02d}.png').as_posix()}'")
    concat.write_text("\n".join(lines), encoding="utf-8")
    cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264",
        "-movflags", "+faststart",
        str(mp4_path),
    ]
    subprocess.check_call(cmd)
    print(gif_path, gif_path.stat().st_size)
    print(mp4_path, mp4_path.stat().st_size)


if __name__ == "__main__":
    main()
