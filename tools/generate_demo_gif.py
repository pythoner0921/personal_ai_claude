"""Generate a professional demo GIF for the README."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "assets"
FRAMES_DIR = OUT_DIR / "demo_frames"
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

W, H = 900, 480

# Colors
BG = "#f8fafc"
CARD_BG = "#ffffff"
CARD_BORDER = "#e2e8f0"
TEXT_PRIMARY = "#0f172a"
TEXT_SECONDARY = "#475569"
TEXT_MUTED = "#94a3b8"
BLUE = "#3b82f6"
BLUE_BG = "#eff6ff"
BLUE_BORDER = "#bfdbfe"
PURPLE = "#7c3aed"
PURPLE_BG = "#f5f3ff"
PURPLE_BORDER = "#c4b5fd"
GREEN = "#059669"
GREEN_BG = "#ecfdf5"
GREEN_BORDER = "#a7f3d0"
AMBER = "#d97706"
AMBER_BG = "#fffbeb"
AMBER_BORDER = "#fde68a"
TEAL = "#0d9488"
TEAL_BG = "#f0fdfa"
TEAL_BORDER = "#99f6e4"
ROSE = "#e11d48"

# Fonts
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("segoeuib.ttf" if bold else "segoeui.ttf", size)

def mono(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("consola.ttf", size)

F_TITLE = font(13, bold=True)
F_STEP = font(11, bold=True)
F_BODY = font(14)
F_BODY_B = font(14, bold=True)
F_BODY_S = font(12)
F_BODY_SB = font(12, bold=True)
F_MONO = mono(12)
F_MONO_S = mono(11)
F_LABEL = font(10, bold=True)
F_SMALL = font(10)
F_TAG = font(9, bold=True)


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def draw_rounded_rect(draw: ImageDraw.ImageDraw, xy: tuple, radius: int,
                       fill: str | None = None, outline: str | None = None, width: int = 1):
    x0, y0, x1, y1 = xy
    if fill:
        draw.rounded_rectangle(xy, radius=radius, fill=hex_to_rgb(fill),
                                outline=hex_to_rgb(outline) if outline else None, width=width)
    elif outline:
        draw.rounded_rectangle(xy, radius=radius, outline=hex_to_rgb(outline), width=width)


def draw_tag(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, bg: str, fg: str, border: str):
    tw = draw.textlength(text, font=F_TAG)
    draw_rounded_rect(draw, (x, y, x + tw + 14, y + 20), 4, fill=bg, outline=border)
    draw.text((x + 7, y + 3), text, fill=hex_to_rgb(fg), font=F_TAG)
    return int(tw + 14)


def draw_arrow_down(draw: ImageDraw.ImageDraw, x: int, y0: int, y1: int, color: str = TEXT_MUTED):
    c = hex_to_rgb(color)
    draw.line([(x, y0), (x, y1 - 6)], fill=c, width=2)
    draw.polygon([(x - 4, y1 - 8), (x + 4, y1 - 8), (x, y1)], fill=c)


def new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), hex_to_rgb(BG))
    draw = ImageDraw.Draw(img)
    return img, draw


def draw_header(draw: ImageDraw.ImageDraw, step_num: int, step_total: int, step_label: str):
    # Top bar
    draw_rounded_rect(draw, (0, 0, W, 44), 0, fill="#f1f5f9", outline=CARD_BORDER)
    draw.text((24, 12), "Personal AI Memory Engine", fill=hex_to_rgb(TEXT_PRIMARY), font=F_TITLE)
    # Step indicator
    step_text = f"Step {step_num}/{step_total}"
    sw = draw.textlength(step_text, font=F_STEP)
    draw.text((W - 24 - sw, 14), step_text, fill=hex_to_rgb(BLUE), font=F_STEP)
    # Step label below
    draw.text((24, 50), step_label, fill=hex_to_rgb(TEXT_SECONDARY), font=F_STEP)


def draw_progress_dots(draw: ImageDraw.ImageDraw, current: int, total: int):
    dot_r = 4
    gap = 16
    total_w = total * (dot_r * 2) + (total - 1) * gap
    sx = (W - total_w) // 2
    y = H - 20
    for i in range(total):
        cx = sx + i * (dot_r * 2 + gap) + dot_r
        if i + 1 == current:
            draw.ellipse((cx - dot_r, y - dot_r, cx + dot_r, y + dot_r), fill=hex_to_rgb(BLUE))
        elif i + 1 < current:
            draw.ellipse((cx - dot_r, y - dot_r, cx + dot_r, y + dot_r), fill=hex_to_rgb(BLUE_BORDER))
        else:
            draw.ellipse((cx - dot_r, y - dot_r, cx + dot_r, y + dot_r), fill=hex_to_rgb(CARD_BORDER))


# ─── Frame 1: User says ──────────────────────────────────────

def frame_1() -> Image.Image:
    img, draw = new_canvas()
    draw_header(draw, 1, 7, "User gives natural feedback")
    draw_progress_dots(draw, 1, 7)

    # Chat bubble
    draw_rounded_rect(draw, (60, 90, W - 60, 200), 12, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw_tag(draw, 76, 102, "USER", BLUE_BG, BLUE, BLUE_BORDER)
    draw.text((76, 134), '"Please keep responses concise', fill=hex_to_rgb(TEXT_PRIMARY), font=F_BODY)
    draw.text((76, 156), ' and start with a short summary."', fill=hex_to_rgb(TEXT_PRIMARY), font=F_BODY)

    # Arrow
    draw_arrow_down(draw, W // 2, 210, 250, BLUE)

    # Observation card
    draw_rounded_rect(draw, (60, 256, W - 60, 380), 12, fill=AMBER_BG, outline=AMBER_BORDER, width=2)
    draw_tag(draw, 76, 268, "CAPTURE", AMBER_BG, AMBER, AMBER_BORDER)
    draw.text((76, 300), "Keyword markers detected:", fill=hex_to_rgb(TEXT_SECONDARY), font=F_BODY_S)
    draw.text((76, 322), "concise", fill=hex_to_rgb(AMBER), font=F_MONO)
    draw.text((170, 322), "summary", fill=hex_to_rgb(AMBER), font=F_MONO)
    draw.text((274, 322), "short", fill=hex_to_rgb(AMBER), font=F_MONO)
    draw.text((76, 348), "Hook: UserPromptSubmit → capture_from_hook_input()", fill=hex_to_rgb(TEXT_MUTED), font=F_SMALL)

    return img


# ─── Frame 2: System learns ──────────────────────────────────

def frame_2() -> Image.Image:
    img, draw = new_canvas()
    draw_header(draw, 2, 7, "Preferences extracted and stored")
    draw_progress_dots(draw, 2, 7)

    # Extraction card
    draw_rounded_rect(draw, (60, 90, W - 60, 220), 12, fill=PURPLE_BG, outline=PURPLE_BORDER, width=2)
    draw_tag(draw, 76, 102, "EXTRACT", PURPLE_BG, PURPLE, PURPLE_BORDER)

    draw.text((76, 134), "Behavioral patterns identified:", fill=hex_to_rgb(TEXT_SECONDARY), font=F_BODY_S)

    # Preference chips
    draw_rounded_rect(draw, (76, 160, 320, 188), 6, fill=CARD_BG, outline=PURPLE_BORDER)
    draw.text((90, 166), "prefers concise output", fill=hex_to_rgb(PURPLE), font=F_MONO_S)

    draw_rounded_rect(draw, (340, 160, 640, 188), 6, fill=CARD_BG, outline=PURPLE_BORDER)
    draw.text((354, 166), "prefers summary before details", fill=hex_to_rgb(PURPLE), font=F_MONO_S)

    draw_arrow_down(draw, W // 2, 228, 268, PURPLE)

    # Storage card
    draw_rounded_rect(draw, (60, 274, W - 60, 420), 12, fill=GREEN_BG, outline=GREEN_BORDER, width=2)
    draw_tag(draw, 76, 286, "MEMORY STORE", GREEN_BG, GREEN, GREEN_BORDER)

    # Lifecycle visualization
    y = 320
    states = [("candidate", TEXT_MUTED), ("recent", AMBER), ("stable", GREEN)]
    cx = 100
    for i, (label, color) in enumerate(states):
        tw = draw.textlength(label, font=F_BODY_SB)
        draw_rounded_rect(draw, (cx, y, cx + tw + 20, y + 28), 5, fill=CARD_BG, outline=color, width=2)
        draw.text((cx + 10, y + 5), label, fill=hex_to_rgb(color), font=F_BODY_SB)
        next_x = cx + tw + 20
        if i < len(states) - 1:
            draw.text((next_x + 8, y + 4), "→", fill=hex_to_rgb(TEXT_MUTED), font=F_BODY_B)
            cx = next_x + 32
        else:
            cx = next_x

    draw.text((76, 364), "stable_preferences.yaml", fill=hex_to_rgb(GREEN), font=F_MONO_S)
    draw.text((340, 364), "confidence: 0.95", fill=hex_to_rgb(TEXT_SECONDARY), font=F_MONO_S)
    draw.text((76, 386), "recent_tendencies.yaml", fill=hex_to_rgb(AMBER), font=F_MONO_S)
    draw.text((340, 386), "confidence: 0.62", fill=hex_to_rgb(TEXT_SECONDARY), font=F_MONO_S)

    return img


# ─── Frame 3: New query arrives ──────────────────────────────

def frame_3() -> Image.Image:
    img, draw = new_canvas()
    draw_header(draw, 3, 7, "Later: user asks a new question")
    draw_progress_dots(draw, 3, 7)

    # Chat bubble
    draw_rounded_rect(draw, (60, 90, W - 60, 190), 12, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw_tag(draw, 76, 102, "USER", BLUE_BG, BLUE, BLUE_BORDER)
    draw.text((76, 134), '"Design an architecture upgrade', fill=hex_to_rgb(TEXT_PRIMARY), font=F_BODY)
    draw.text((76, 156), ' for my system."', fill=hex_to_rgb(TEXT_PRIMARY), font=F_BODY)

    draw_arrow_down(draw, W // 2, 200, 240, BLUE)

    # Task classification
    draw_rounded_rect(draw, (60, 246, W - 60, 380), 12, fill=PURPLE_BG, outline=PURPLE_BORDER, width=2)
    draw_tag(draw, 76, 258, "TASK CLASSIFIER", PURPLE_BG, PURPLE, PURPLE_BORDER)

    draw.text((76, 292), "Detected type:", fill=hex_to_rgb(TEXT_SECONDARY), font=F_BODY_S)
    draw_rounded_rect(draw, (210, 284, 360, 312), 6, fill=CARD_BG, outline=PURPLE_BORDER, width=2)
    draw.text((224, 288), "architecture", fill=hex_to_rgb(PURPLE), font=F_BODY_B)

    draw.text((76, 324), "Affinity boost for:", fill=hex_to_rgb(TEXT_SECONDARY), font=F_BODY_S)
    draw.text((230, 324), "summary  +0.2", fill=hex_to_rgb(GREEN), font=F_MONO_S)
    draw.text((400, 324), "table  +0.2", fill=hex_to_rgb(GREEN), font=F_MONO_S)
    draw.text((540, 324), "modular  +0.2", fill=hex_to_rgb(GREEN), font=F_MONO_S)

    draw.text((76, 354), "Hook: UserPromptSubmit → classify_task() → task_affinity_bonus()", fill=hex_to_rgb(TEXT_MUTED), font=F_SMALL)

    return img


# ─── Frame 4: Ranking selects ────────────────────────────────

def frame_4() -> Image.Image:
    img, draw = new_canvas()
    draw_header(draw, 4, 7, "Ranking engine selects top preferences")
    draw_progress_dots(draw, 4, 7)

    # Formula card
    draw_rounded_rect(draw, (60, 86, W - 60, 130), 10, fill="#f1f5f9", outline=CARD_BORDER)
    draw.text((76, 96), "score = priority×3 + confidence×decay + relevance + scope + affinity",
              fill=hex_to_rgb(TEXT_SECONDARY), font=F_MONO_S)

    # Ranking table
    draw_rounded_rect(draw, (60, 144, W - 60, 400), 12, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw_tag(draw, 76, 156, "RANKING ENGINE", BLUE_BG, BLUE, BLUE_BORDER)

    # Table header
    y = 192
    draw.text((76, y), "Preference", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.text((420, y), "Conf", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.text((490, y), "Decay", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.text((560, y), "Affinity", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.text((640, y), "Score", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.text((710, y), "Selected", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.line([(76, y + 16), (W - 76, y + 16)], fill=hex_to_rgb(CARD_BORDER), width=1)

    # Rows
    rows = [
        ("summary before details",    "0.95", "1.00", "+0.2", "10.35", True),
        ("table format for comparison","0.94", "1.00", "+0.2", "10.34", True),
        ("concise output",            "0.78", "1.00", "+0.2", "10.18", True),
        ("modular over big rewrites", "0.81", "0.77", "+0.2", " 9.82", True),
        ("compact command style",     "0.62", "0.77", " 0.0", " 6.48", False),
    ]
    for i, (desc, conf, decay, aff, score, selected) in enumerate(rows):
        ry = y + 24 + i * 32
        if selected:
            draw_rounded_rect(draw, (72, ry - 4, W - 72, ry + 24), 4, fill=GREEN_BG)
        fg = TEXT_PRIMARY if selected else TEXT_MUTED
        draw.text((80, ry), desc, fill=hex_to_rgb(fg), font=F_MONO_S)
        draw.text((424, ry), conf, fill=hex_to_rgb(fg), font=F_MONO_S)
        draw.text((494, ry), decay, fill=hex_to_rgb(fg), font=F_MONO_S)
        draw.text((564, ry), aff, fill=hex_to_rgb(GREEN if aff.strip() != "0.0" else TEXT_MUTED), font=F_MONO_S)
        draw.text((640, ry), score, fill=hex_to_rgb(fg), font=F_MONO_S)
        mark = "●" if selected else "○"
        draw.text((726, ry), mark, fill=hex_to_rgb(GREEN if selected else TEXT_MUTED), font=F_BODY_B)

    return img


# ─── Frame 5: Context injected ───────────────────────────────

def frame_5() -> Image.Image:
    img, draw = new_canvas()
    draw_header(draw, 5, 7, "Context injected into Claude")
    draw_progress_dots(draw, 5, 7)

    # Injection payload
    draw_rounded_rect(draw, (60, 90, W - 60, 380), 12, fill=CARD_BG, outline=BLUE_BORDER, width=2)
    draw_tag(draw, 76, 102, "INJECTED CONTEXT", BLUE_BG, BLUE, BLUE_BORDER)

    y = 138
    lines = [
        ("User Profile (reflections)", TEXT_SECONDARY, F_BODY_SB),
        ("- Communication: lead with summaries, use tables, keep concise.", TEAL, F_BODY_S),
        ("- Code approach: prefer modular incremental changes.", TEAL, F_BODY_S),
        ("", TEXT_PRIMARY, F_BODY_S),
        ("Personal Preferences", TEXT_SECONDARY, F_BODY_SB),
        ("Project: personal_ai_claude", TEXT_MUTED, F_BODY_S),
        ("Apply unless user overrides:", TEXT_MUTED, F_BODY_S),
        ("- (0.95) prefers summary before details", TEXT_PRIMARY, F_MONO_S),
        ("- (0.94) prefers table format for comparison", TEXT_PRIMARY, F_MONO_S),
        ("- (0.78) prefers concise output", TEXT_PRIMARY, F_MONO_S),
        ("- (0.81) prefers modular changes over big rewrites", TEXT_PRIMARY, F_MONO_S),
    ]
    for text, color, f in lines:
        if text:
            draw.text((80, y), text, fill=hex_to_rgb(color), font=f)
        y += 20

    # Note at bottom
    draw_rounded_rect(draw, (60, 392, W - 60, 432), 8, fill="#f1f5f9", outline=CARD_BORDER)
    draw.text((76, 402), "Hook: SessionStart + UserPromptSubmit → build_injection_payload()",
              fill=hex_to_rgb(TEXT_MUTED), font=F_SMALL)

    return img


# ─── Frame 6: Response shaped ────────────────────────────────

def frame_6() -> Image.Image:
    img, draw = new_canvas()
    draw_header(draw, 6, 7, "Claude responds in learned style")
    draw_progress_dots(draw, 6, 7)

    # Response card
    draw_rounded_rect(draw, (60, 90, W - 60, 420), 12, fill=CARD_BG, outline=GREEN_BORDER, width=2)
    draw_tag(draw, 76, 102, "CLAUDE RESPONSE", GREEN_BG, GREEN, GREEN_BORDER)

    y = 136
    draw.text((76, y), "Summary:", fill=hex_to_rgb(TEXT_PRIMARY), font=F_BODY_B)
    y += 24
    draw.text((76, y), "Upgrade to event-driven pipeline with 3 modules.", fill=hex_to_rgb(TEXT_PRIMARY), font=F_BODY_S)
    y += 28

    # Mini table
    draw_rounded_rect(draw, (76, y, W - 76, y + 120), 8, fill="#f8fafc", outline=CARD_BORDER)
    ty = y + 8
    draw.text((92, ty), "Approach", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.text((320, ty), "Effort", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.text((480, ty), "Risk", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.text((620, ty), "Recommendation", fill=hex_to_rgb(TEXT_MUTED), font=F_LABEL)
    draw.line([(92, ty + 16), (W - 92, ty + 16)], fill=hex_to_rgb(CARD_BORDER))

    table_rows = [
        ("Modular refactor", "Low", "Low", "Recommended"),
        ("Full rewrite",     "High", "High", "—"),
        ("Hybrid approach",  "Medium", "Medium", "Alternative"),
    ]
    for i, (a, b, c, d) in enumerate(table_rows):
        ry = ty + 24 + i * 24
        draw.text((92, ry), a, fill=hex_to_rgb(TEXT_PRIMARY), font=F_BODY_S)
        draw.text((320, ry), b, fill=hex_to_rgb(TEXT_SECONDARY), font=F_BODY_S)
        draw.text((480, ry), c, fill=hex_to_rgb(TEXT_SECONDARY), font=F_BODY_S)
        color = GREEN if d == "Recommended" else TEXT_SECONDARY
        draw.text((620, ry), d, fill=hex_to_rgb(color), font=F_BODY_S)

    y += 132

    # Annotations
    checks = [
        "Summary first",
        "Table comparison",
        "Concise style",
        "Modular approach",
    ]
    for i, label in enumerate(checks):
        cx = 76 + i * 190
        # Green dot instead of unicode checkmark for font compatibility
        draw.ellipse((cx, y + 5, cx + 8, y + 13), fill=hex_to_rgb(GREEN))
        draw.text((cx + 14, y + 1), label, fill=hex_to_rgb(GREEN), font=F_BODY_SB)

    return img


# ─── Frame 7: Reflection ─────────────────────────────────────

def frame_7() -> Image.Image:
    img, draw = new_canvas()
    draw_header(draw, 7, 7, "System generates reflection summary")
    draw_progress_dots(draw, 7, 7)

    # Reflection card
    draw_rounded_rect(draw, (60, 90, W - 60, 280), 12, fill=TEAL_BG, outline=TEAL_BORDER, width=2)
    draw_tag(draw, 76, 102, "REFLECTION ENGINE", TEAL_BG, TEAL, TEAL_BORDER)

    y = 140
    draw.text((76, y), "Synthesized from 6 preferences across 12 sessions:", fill=hex_to_rgb(TEXT_SECONDARY), font=F_BODY_S)
    y += 30
    draw.text((76, y), '"User prefers concise, summary-first,', fill=hex_to_rgb(TEAL), font=F_BODY)
    y += 22
    draw.text((76, y), ' structured responses with tables."', fill=hex_to_rgb(TEAL), font=F_BODY)
    y += 30
    draw.text((76, y), "→  reflections.yaml  |  triggered every 50 events", fill=hex_to_rgb(TEXT_MUTED), font=F_MONO_S)

    # Health card
    draw_rounded_rect(draw, (60, 296, W - 60, 430), 12, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw_tag(draw, 76, 308, "MEMORY HEALTH", "#f1f5f9", TEXT_SECONDARY, CARD_BORDER)

    y = 344
    health_lines = [
        ("Active preferences:", "6", "(stable=4, recent=2)"),
        ("Avg confidence:", "80%", ""),
        ("Duplicate candidates:", "0", ""),
        ("Archived:", "0", ""),
    ]
    for label, val, note in health_lines:
        draw.text((80, y), label, fill=hex_to_rgb(TEXT_SECONDARY), font=F_BODY_S)
        draw.text((280, y), val, fill=hex_to_rgb(BLUE), font=F_BODY_B)
        if note:
            draw.text((320, y), note, fill=hex_to_rgb(TEXT_MUTED), font=F_BODY_S)
        y += 22

    return img


# ─── Assemble GIF ────────────────────────────────────────────

def main():
    generators = [frame_1, frame_2, frame_3, frame_4, frame_5, frame_6, frame_7]
    frames: list[Image.Image] = []

    for i, gen in enumerate(generators):
        img = gen()
        img.save(FRAMES_DIR / f"frame_{i+1}.png")
        # Convert to P mode for smaller GIF
        frames.append(img.quantize(colors=128, method=2))

    # Durations in ms: each frame visible ~1.4s, pause longer on frame 4 (ranking) and 6 (result)
    durations = [1400, 1400, 1400, 2200, 1800, 2200, 2000]

    out_path = OUT_DIR / "demo.gif"
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )

    size_kb = out_path.stat().st_size / 1024
    print(f"GIF saved to {out_path}  ({size_kb:.0f} KB)")
    print(f"Frames saved to {FRAMES_DIR}/")


if __name__ == "__main__":
    main()
