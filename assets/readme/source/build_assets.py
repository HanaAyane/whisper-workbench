#!/usr/bin/env python3
"""Deterministic SVG builder for the Whisper工作台 README.

Palette, type and layout are frozen here so hero.svg / pipeline.svg stay
hand-editable and reproducible. Run: python build_assets.py
"""
from __future__ import annotations
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent

INK = "#14182A"
INK2 = "#39435A"
MUT = "#6C7690"
PRIMARY = "#4D42B8"
PRIMARY_D = "#3C328F"
PL = "#6C5CE7"
SOFT = "#E7E3FB"
SOFT2 = "#F6F5FE"
LINEC = "#DBDFEF"
GREEN = "#0E7A5F"
GREEN_SOFT = "#DDF3EA"
AMBER = "#94600D"
AMBER_SOFT = "#FCF3DF"
AMBER_LINE = "#E7C88B"

SANS = "'Segoe UI','Microsoft YaHei UI','PingFang SC','Hiragino Sans','Yu Gothic UI',system-ui,sans-serif"
MONO = "'Cascadia Code','SFMono-Regular',Consolas,'Liberation Mono',monospace"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text_w(s: str, size: float) -> float:
    """Rough advance width: CJK ~1em, ASCII ~0.56em, space ~0.3em."""
    w = 0.0
    for ch in s:
        if ord(ch) > 0x2E80:
            w += 1.0
        elif ch == " ":
            w += 0.30
        else:
            w += 0.56
    return w * size


def hero() -> str:
    W, H = 1200, 460
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d" font-family="{SANS}">')
    p.append('<title id="t">Whisper工作台 —— 本地日语字幕工作台</title>')
    p.append('<desc id="d">标题与一句话说明：把日语音频变成可编辑、可导出的双语字幕，转录、翻译、术语复核与导出全部在本机完成。右侧是界面示意图，展示音频波形转成带时间码的日语字幕并导出 SRT、VTT、LRC、TXT。</desc>')
    p.append('<defs>')
    p.append('<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">')
    p.append('<stop offset="0" stop-color="#F3F4FD"/><stop offset="0.55" stop-color="#EEF1FB"/><stop offset="1" stop-color="#E9F2FB"/>')
    p.append('</linearGradient>')
    p.append('<linearGradient id="wave" x1="0" y1="0" x2="0" y2="1">')
    p.append(f'<stop offset="0" stop-color="{PL}"/><stop offset="1" stop-color="{PRIMARY}"/></linearGradient>')
    p.append('</defs>')
    p.append(f'<rect width="{W}" height="{H}" rx="28" fill="url(#bg)"/>')

    # left title block
    p.append('<g transform="translate(72 80)">')
    p.append(f'<text x="0" y="0" font-size="17" font-weight="700" letter-spacing="4" fill="{PRIMARY}">日语 · 本地字幕工作台</text>')
    p.append(f'<text x="-2" y="80" font-size="78" font-weight="800" letter-spacing="-1.5" fill="{INK}">Whisper 工作台</text>')
    bars = [10, 16, 24, 14, 30, 20, 12, 26, 34, 18, 10, 22, 30, 16, 24, 12, 28, 18, 8, 14]
    bx = 2
    for h in bars:
        p.append(f'<rect x="{bx}" y="{round(120 - h)}" width="5" height="{h}" rx="2.5" fill="url(#wave)" opacity="0.9"/>')
        bx += 9
    p.append(f'<text x="0" y="196" font-size="22" fill="{INK2}">把日语音频，变成可编辑、可导出的双语字幕。</text>')
    p.append(f'<text x="0" y="230" font-size="22" fill="{INK2}">转录、翻译、术语复核与导出，全部在本机完成。</text>')

    pills = [("音频不出机", GREEN), ("本地 CT2 推理", PRIMARY), ("可选 DeepSeek 翻译", PRIMARY)]
    px, py, ph = 0, 268, 40
    for label, dot in pills:
        w = int(text_w(label, 16) + 44)
        p.append(f'<rect x="{px}" y="{py}" width="{w}" height="{ph}" rx="20" fill="#FFFFFF" fill-opacity="0.72" stroke="{LINEC}" stroke-width="1.2"/>')
        p.append(f'<circle cx="{px + 18}" cy="{py + ph/2}" r="4.5" fill="{dot}"/>')
        p.append(f'<text x="{px + 30}" y="{py + 26}" font-size="16" font-weight="600" fill="{INK2}">{esc(label)}</text>')
        px += w + 12

    p.append(f'<text x="0" y="356" font-size="14" fill="{MUT}" font-family="{MONO}">v0.2.0 · Electron 45 · React 18 · faster-whisper 1.2</text>')
    p.append('</g>')

    # right illustrative workbench card
    p.append('<g transform="translate(660 70)">')
    p.append('<rect x="5" y="9" width="468" height="332" rx="20" fill="#1A1F3A" opacity="0.06"/>')
    p.append(f'<rect x="0" y="0" width="468" height="332" rx="20" fill="#FFFFFF" stroke="{LINEC}" stroke-width="1.4"/>')
    p.append(f'<circle cx="26" cy="32" r="5" fill="{GREEN}"/>')
    p.append(f'<text x="40" y="37" font-size="15" font-weight="600" fill="{GREEN}">本地服务就绪</text>')
    p.append(f'<text x="444" y="37" text-anchor="end" font-size="13" fill="{MUT}">字幕复核 · 示意</text>')
    p.append(f'<line x1="22" y1="56" x2="446" y2="56" stroke="{LINEC}" stroke-width="1"/>')
    bx = 26
    i = 0
    while bx < 444:
        h = 6 + int(16 * (0.35 + 0.65 * abs(math.sin(i * 1.7))))
        p.append(f'<rect x="{bx}" y="{96 - h/2}" width="4" height="{h}" rx="2" fill="{PL}" opacity="0.55"/>')
        bx += 9
        i += 1
    p.append(f'<path d="M234 108 L234 122 M228 116 L234 123 L240 116" stroke="{MUT}" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')

    def sub(y, tc, jp):
        p.append(f'<rect x="24" y="{y}" width="420" height="70" rx="12" fill="{SOFT2}" stroke="#E2DEF8" stroke-width="1"/>')
        p.append(f'<text x="40" y="{y+25}" font-size="13" fill="{PRIMARY}" font-family="{MONO}">{esc(tc)}</text>')
        p.append(f'<text x="40" y="{y+50}" font-size="17" fill="{INK}">{esc(jp)}</text>')

    sub(132, "00:00:01,200", "田中さんと渋谷で会いました。")
    sub(212, "00:00:04,350", "明日の会議は十時からです。")
    cx = 26
    for f in ["SRT", "VTT", "LRC", "TXT"]:
        w = int(text_w(f, 12) + 22)
        p.append(f'<rect x="{cx}" y="296" width="{w}" height="22" rx="11" fill="{SOFT}"/>')
        p.append(f'<text x="{cx + 11}" y="311" font-size="12" font-weight="700" fill="{PRIMARY_D}" font-family="{MONO}">{f}</text>')
        cx += w + 8
    p.append(f'<text x="444" y="311" text-anchor="end" font-size="12" fill="{MUT}">导出格式</text>')
    p.append('</g>')
    p.append('</svg>')
    return "\n".join(p)


def pipeline() -> str:
    W, H = 1200, 380
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d" font-family="{SANS}">')
    p.append('<title id="t">Whisper工作台的工作流与数据边界</title>')
    p.append('<desc id="d">六步本地流水线：音频或媒体输入、PyAV 解码、VAD 切分、faster-whisper 本地转录、术语复核、导出字幕；下方单独标出可选的 DeepSeek 翻译只发送待翻译字幕文本。</desc>')
    p.append(f'<rect width="{W}" height="{H}" rx="24" fill="#F7F8FD"/>')
    p.append(f'<text x="56" y="66" font-size="30" font-weight="800" fill="{INK}">本地优先的工作流</text>')
    p.append(f'<text x="56" y="98" font-size="17" fill="{MUT}">解码、VAD、ASR、术语复核与导出都在本机；只有启用翻译时才把待翻译字幕文本发给 DeepSeek。</text>')
    p.append(f'<rect x="934" y="44" width="210" height="40" rx="20" fill="{GREEN_SOFT}"/>')
    p.append(f'<circle cx="958" cy="64" r="4.5" fill="{GREEN}"/>')
    p.append(f'<text x="972" y="70" font-size="15" font-weight="700" fill="{GREEN}">音频不出本机</text>')

    start, w = 56, 160
    gap = (1088 - 6 * w) / 5
    y, h = 148, 92
    boxes = [
        ("1", "音频 / 媒体", ["WAV · MP3 · M4A", "FLAC · MP4 · WEBM"]),
        ("2", "PyAV 解码", ["16 kHz · 单声道", "float32"]),
        ("3", "VAD 切分", ["ONNX 优先", "≤ 30 秒 / 块"]),
        ("4", "faster-whisper", ["本地 CTranslate2", "int8 / bfloat16"]),
        ("5", "术语复核", ["原文纠错", "译名统一 · 仅高亮"]),
        ("6", "导出字幕", ["SRT · VTT", "LRC · TXT"]),
    ]
    centers = []
    for i, (num, title, subs) in enumerate(boxes):
        bx = start + i * (w + gap)
        centers.append(bx + w / 2)
        p.append(f'<rect x="{bx:.1f}" y="{y}" width="{w}" height="{h}" rx="14" fill="#FFFFFF" stroke="{LINEC}" stroke-width="1.3"/>')
        p.append(f'<circle cx="{bx+22:.1f}" cy="{y+23}" r="12" fill="{SOFT}"/>')
        p.append(f'<text x="{bx+22:.1f}" y="{y+28}" text-anchor="middle" font-size="13" font-weight="700" fill="{PRIMARY_D}">{num}</text>')
        p.append(f'<text x="{bx+42:.1f}" y="{y+29}" font-size="17" font-weight="700" fill="{INK}">{esc(title)}</text>')
        p.append(f'<text x="{bx+18:.1f}" y="{y+56}" font-size="13.5" fill="{MUT}">{esc(subs[0])}</text>')
        p.append(f'<text x="{bx+18:.1f}" y="{y+77}" font-size="13.5" fill="{MUT}">{esc(subs[1])}</text>')
        if i < len(boxes) - 1:
            ax = bx + w
            p.append(f'<path d="M{ax+4:.1f} {y+h/2} L{ax+gap-6:.1f} {y+h/2}" stroke="#B9C0D6" stroke-width="2" stroke-linecap="round"/>')
            p.append(f'<path d="M{ax+gap-10:.1f} {y+h/2-4} L{ax+gap-4:.1f} {y+h/2} L{ax+gap-10:.1f} {y+h/2+4}" fill="none" stroke="#B9C0D6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')

    p.append(f'<text x="{W/2}" y="268" text-anchor="middle" font-size="15" font-weight="600" fill="{GREEN}">以上解码、VAD、ASR、术语复核与导出全部在本机执行，音频不上传。</text>')

    by = 300
    p.append(f'<path d="M{centers[3]:.1f} {y+h} L{centers[3]:.1f} {by}" stroke="{AMBER_LINE}" stroke-width="2" stroke-dasharray="5 5"/>')
    p.append(f'<rect x="56" y="{by}" width="1088" height="56" rx="12" fill="{AMBER_SOFT}" stroke="{AMBER_LINE}" stroke-width="1.3"/>')
    p.append(f'<circle cx="82" cy="{by+28}" r="5" fill="{AMBER}"/>')
    p.append(f'<text x="98" y="{by+34}" font-size="17" font-weight="700" fill="{AMBER}">可选 · DeepSeek 翻译</text>')
    p.append(f'<text x="270" y="{by+34}" font-size="15" fill="{INK2}">启用翻译时仅把待翻译字幕文本发送到 api.deepseek.com，音频与文件都不上传。</text>')
    p.append('</svg>')
    return "\n".join(p)


if __name__ == "__main__":
    (OUT / "hero.svg").write_text(hero(), encoding="utf-8")
    (OUT / "pipeline.svg").write_text(pipeline(), encoding="utf-8")
    print("wrote hero.svg and pipeline.svg")
