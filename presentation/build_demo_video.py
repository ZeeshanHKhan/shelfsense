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


def crop_shot(name):
    img = Image.open(SHOTS / name).convert("RGB").crop((0, 0, W, H))
    return img


def main():
    frames = [
        (card("ShelfSense", [
            "On-prem store price compliance.",
            "Watch it here. Nothing to install.",
        ]), 3.0),
        (card("How it works", [
            "1. The phone reads the barcode and the printed price. The photo stays on the device.",
            "2. The laptop compares those numbers with the store price list.",
            "3. llama3.2:3b, a local 3-billion-parameter model, writes the associate task.",
        ], BLUE), 5.0),
        (crop_shot("demo-01-empty.png"), 3.0),
        (card("A correct label", [
            "Cola matches the price list.",
            "The dashboard stays clear. Only the barcode and the price crossed the network.",
        ], GREEN), 4.0),
        (crop_shot("demo-02-match.png"), 3.5),
        (card("A wrong shelf price", [
            "AA Batteries: the label says $9.99 and the system says $10.99.",
            "The rule flags the mismatch. llama3.2:3b then writes the one-hour task.",
        ], AMBER), 5.0),
        (crop_shot("demo-03-mismatch.png"), 5.0),
        (card("The other cases", [
            "An unknown barcode and a blurry price still get a task.",
            "Those two use fixed rules. The price mismatch used the local model.",
        ], BLUE), 4.5),
        (crop_shot("demo-04-exceptions.png"), 6.0),
        (card("That is the demo", [
            "The phone reads. The store server decides. The edge model writes the task.",
            "If the model is off, the same task still comes from fixed rules.",
        ], GREEN), 4.5),
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
