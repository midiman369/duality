"""Save a Rich recording as an SVG framed like Windows Terminal (Campbell, PowerShell tab)."""
from html import escape
from rich.terminal_theme import TerminalTheme

# Windows Terminal "Campbell" scheme.
CAMPBELL = TerminalTheme(
    (12, 12, 12), (204, 204, 204),
    [(12, 12, 12), (197, 15, 31), (19, 161, 14), (193, 156, 0), (0, 55, 218),
     (136, 23, 152), (58, 150, 221), (204, 204, 204)],
    [(118, 118, 118), (231, 72, 86), (22, 198, 12), (249, 241, 165), (59, 120, 255),
     (180, 0, 158), (97, 214, 214), (242, 242, 242)],
)

FONT = "'Cascadia Mono', 'Cascadia Code', Consolas, 'DejaVu Sans Mono', 'Liberation Mono', monospace"
UI = "'Segoe UI', 'Segoe UI Variable', Tahoma, 'DejaVu Sans', Arial, sans-serif"


def _template(tab: str) -> str:
    tab = escape(tab).replace("{", "{{").replace("}", "}}")
    return """<svg class="rich-terminal" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <!-- Rendered by Duality docs (Rich export, Windows Terminal frame) -->
    <style>
    .{unique_id}-matrix {{
        font-family: %(font)s;
        font-size: {char_height}px;
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}
    .{unique_id}-ui {{ font-family: %(ui)s; font-size: 12px; fill: #ffffff; }}
    .{unique_id}-glyph {{ stroke: #cccccc; stroke-width: 1; fill: none; }}
    {styles}
    </style>
    <defs>
    <clipPath id="{unique_id}-clip-terminal">
      <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}" />
    </clipPath>
    {lines}
    </defs>

    <!-- window -->
    <clipPath id="{unique_id}-win"><rect x="0" y="0" width="{width}" height="{height}" rx="8"/></clipPath>
    <g clip-path="url(#{unique_id}-win)">
      <rect x="0" y="0" width="{width}" height="{height}" fill="#0c0c0c"/>
      <rect x="0" y="0" width="{width}" height="38" fill="#202020"/>
    </g>
    <rect x="0.5" y="0.5" width="{width}" height="{height}" rx="8" fill="none" stroke="#3a3a3a" transform="translate(-0.5 -0.5)"/>
    <!-- active tab -->
    <path d="M8 38 V14 A6 6 0 0 1 14 8 H236 A6 6 0 0 1 242 14 V38 Z" fill="#0c0c0c"/>
    <rect x="18" y="16" width="16" height="14" rx="2.5" fill="#2c78d4"/>
    <path d="M21.5 19.5 L25.5 23 L21.5 26.5" stroke="#ffffff" stroke-width="1.6" fill="none" stroke-linecap="round"/>
    <path d="M26.5 27 H31" stroke="#ffffff" stroke-width="1.4" stroke-linecap="round"/>
    <text class="{unique_id}-ui" x="44" y="27.5">%(tab)s</text>
    <path class="{unique_id}-glyph" d="M221 19 L229 27 M229 19 L221 27"/>
    <!-- new tab + dropdown -->
    <path class="{unique_id}-glyph" d="M261 18 V30 M255 24 H267"/>
    <path class="{unique_id}-glyph" d="M287 22 L291 26 L295 22"/>
    <!-- window buttons -->
    <g transform="translate({width}, 0)">
      <path class="{unique_id}-glyph" d="M-120 20.5 H-110"/>
      <rect class="{unique_id}-glyph" x="-74.5" y="15.5" width="10" height="10"/>
      <path class="{unique_id}-glyph" d="M-28 15 L-18 25 M-18 15 L-28 25"/>
    </g>

    <g transform="translate({terminal_x}, {terminal_y})" clip-path="url(#{unique_id}-clip-terminal)">
    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
    </g>
</svg>
""" % {"font": FONT, "ui": UI, "tab": tab}


def save_wt(console, path: str, tab: str = "Windows PowerShell") -> None:
    svg = console.export_svg(title="", theme=CAMPBELL, code_format=_template(tab))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
