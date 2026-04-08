"""
Genere les diagrammes PNG pour le guide de montage du SumoBot.
Usage: python generate_diagrams.py
Produit: schema_cablage.png, schema_alimentation.png, schema_capteurs.png, schema_pinout.png
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Arc
import numpy as np
import os

# Style commun
BG_COLOR = '#1a1a2e'
PANEL_COLOR = '#16213e'
WIRE_COLORS = {
    'power': '#e74c3c',
    'gnd': '#2c3e50',
    'signal': '#3498db',
    'pwm': '#e67e22',
    'i2c': '#2ecc71',
    'motor': '#9b59b6',
    'line': '#f39c12',
    'laser': '#1abc9c',
}
TEXT_COLOR = '#ecf0f1'
ACCENT = '#e74c3c'

def setup_fig(width, height, title):
    fig, ax = plt.subplots(1, 1, figsize=(width, height), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, color=TEXT_COLOR, fontsize=22, fontweight='bold', pad=20, fontfamily='sans-serif')
    return fig, ax

def draw_box(ax, x, y, w, h, label, color, sublabel=None, fontsize=11):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5",
                          facecolor=color, edgecolor='white', linewidth=1.5, alpha=0.9)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2 + (1.5 if sublabel else 0), label,
            ha='center', va='center', color='white', fontsize=fontsize, fontweight='bold', fontfamily='sans-serif')
    if sublabel:
        ax.text(x + w/2, y + h/2 - 2, sublabel,
                ha='center', va='center', color='#bdc3c7', fontsize=8, fontfamily='sans-serif')

def draw_wire(ax, points, color, label=None, lw=2.5):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.plot(xs, ys, color=color, linewidth=lw, solid_capstyle='round', zorder=2)
    # petit cercle aux jonctions
    for p in points:
        ax.plot(p[0], p[1], 'o', color=color, markersize=4, zorder=3)
    if label:
        mx = (xs[0] + xs[-1]) / 2
        my = (ys[0] + ys[-1]) / 2
        ax.text(mx, my + 1.5, label, ha='center', va='bottom', color=color,
                fontsize=8, fontweight='bold', fontfamily='sans-serif',
                bbox=dict(boxstyle='round,pad=0.2', facecolor=BG_COLOR, edgecolor=color, alpha=0.8))


# =============================================================
# DIAGRAMME 1 : Schema d'alimentation
# =============================================================
def generate_alimentation():
    fig, ax = setup_fig(14, 10, "Schema d'alimentation")

    # Batterie
    draw_box(ax, 35, 82, 30, 12, "BATTERIE", '#c0392b', "NiMH 7.2V", fontsize=14)

    # LM2596
    draw_box(ax, 10, 50, 25, 12, "LM2596", '#2980b9', "Buck 7.2V → 5V")

    # L298N
    draw_box(ax, 65, 50, 25, 12, "L298N", '#8e44ad', "Pont H moteurs")

    # Arduino
    draw_box(ax, 25, 15, 30, 14, "ARDUINO MEGA", '#27ae60', "Pin 5V + Shield")

    # Moteurs
    draw_box(ax, 65, 15, 12, 10, "MOT. G", '#e67e22')
    draw_box(ax, 82, 15, 12, 10, "MOT. D", '#e67e22')

    # Fils batterie -> LM2596 (rouge +)
    draw_wire(ax, [(40, 82), (40, 72), (22, 72), (22, 62)], WIRE_COLORS['power'], "+7.2V")

    # Fils batterie -> L298N (rouge +)
    draw_wire(ax, [(60, 82), (60, 72), (77, 72), (77, 62)], WIRE_COLORS['power'], "+7.2V")

    # LM2596 -> Arduino (vert 5V)
    draw_wire(ax, [(22, 50), (22, 38), (40, 38), (40, 29)], '#2ecc71', "5V")

    # L298N -> Moteurs
    draw_wire(ax, [(72, 50), (71, 25)], WIRE_COLORS['motor'], "OUT1/2")
    draw_wire(ax, [(83, 50), (88, 25)], WIRE_COLORS['motor'], "OUT3/4")

    # GND commun
    ax.plot([22, 22, 88, 88], [5, 5, 5, 5], color=WIRE_COLORS['gnd'], linewidth=4, zorder=1)
    ax.plot([22, 22], [5, 15], color=WIRE_COLORS['gnd'], linewidth=2.5, zorder=2)
    ax.plot([40, 40], [5, 15], color=WIRE_COLORS['gnd'], linewidth=2.5, zorder=2)
    ax.plot([77, 77], [5, 50], color=WIRE_COLORS['gnd'], linewidth=2.5, zorder=2)
    ax.text(55, 2, "GND COMMUN (masse partagee par tous les composants)", ha='center', color='#7f8c8d',
            fontsize=9, fontweight='bold', fontfamily='sans-serif')

    # Avertissement
    ax.text(50, 42, "JAMAIS brancher 7.2V directement sur le pin 5V !",
            ha='center', va='center', color='#e74c3c', fontsize=11, fontweight='bold', fontfamily='sans-serif',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#1a1a2e', edgecolor='#e74c3c', linewidth=2))

    # Legende
    legend_y = 95
    ax.plot([2, 6], [legend_y, legend_y], color=WIRE_COLORS['power'], linewidth=3)
    ax.text(7, legend_y, "7.2V (batterie)", color=TEXT_COLOR, fontsize=8, va='center', fontfamily='sans-serif')
    ax.plot([25, 29], [legend_y, legend_y], color='#2ecc71', linewidth=3)
    ax.text(30, legend_y, "5V (regulee)", color=TEXT_COLOR, fontsize=8, va='center', fontfamily='sans-serif')
    ax.plot([48, 52], [legend_y, legend_y], color=WIRE_COLORS['motor'], linewidth=3)
    ax.text(53, legend_y, "Moteurs", color=TEXT_COLOR, fontsize=8, va='center', fontfamily='sans-serif')
    ax.plot([66, 70], [legend_y, legend_y], color=WIRE_COLORS['gnd'], linewidth=3)
    ax.text(71, legend_y, "GND (masse)", color=TEXT_COLOR, fontsize=8, va='center', fontfamily='sans-serif')

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'schema_alimentation.png'), dpi=180, facecolor=BG_COLOR,
                bbox_inches='tight', pad_inches=0.5)
    plt.close(fig)
    print("  schema_alimentation.png")


# =============================================================
# DIAGRAMME 2 : Schema de cablage complet
# =============================================================
def generate_cablage_complet():
    fig, ax = setup_fig(18, 13, "Schema de cablage complet du SumoBot")

    # --- Batterie ---
    draw_box(ax, 40, 88, 20, 8, "BATTERIE", '#c0392b', "NiMH 7.2V", fontsize=13)

    # --- LM2596 ---
    draw_box(ax, 10, 70, 20, 8, "LM2596", '#2980b9', "7.2V → 5V")

    # --- L298N ---
    draw_box(ax, 70, 70, 20, 8, "L298N", '#8e44ad', "Pont H")

    # --- Arduino Mega + Shield (grand bloc central) ---
    mega_box = FancyBboxPatch((25, 28), 50, 30, boxstyle="round,pad=0.8",
                               facecolor='#1e3a2f', edgecolor='#2ecc71', linewidth=2.5, alpha=0.95)
    ax.add_patch(mega_box)
    ax.text(50, 55, "ARDUINO MEGA 2560 + Shield Sensor", ha='center', va='center',
            color='#2ecc71', fontsize=14, fontweight='bold', fontfamily='sans-serif')

    # Pins sur l'Arduino
    pins_left = [
        ("Pin 10 (ENA)", 47, '#e67e22'),
        ("Pin 9  (IN1)", 44.5, '#e67e22'),
        ("Pin 8  (IN2)", 42, '#e67e22'),
        ("Pin 7  (IN4)", 39.5, '#e67e22'),
        ("Pin 6  (IN3)", 37, '#e67e22'),
        ("Pin 5  (ENB)", 34.5, '#e67e22'),
    ]
    for label, y, color in pins_left:
        ax.text(27, y, label, ha='left', va='center', color=color, fontsize=7.5, fontfamily='monospace')

    pins_right = [
        ("Pin 20 (SDA)", 47, '#2ecc71'),
        ("Pin 21 (SCL)", 44.5, '#2ecc71'),
        ("Pin 22 (XSHUT0)", 42, '#1abc9c'),
        ("Pin 23 (XSHUT1)", 39.5, '#1abc9c'),
        ("Pin 24 (XSHUT2)", 37, '#1abc9c'),
        ("Pin 2  (BTN)", 34.5, '#3498db'),
    ]
    for label, y, color in pins_right:
        ax.text(56, y, label, ha='left', va='center', color=color, fontsize=7.5, fontfamily='monospace')

    ax.text(27, 31, "A0 (ligne G)   A1 (ligne D)   A2 (ligne Arr.)",
            ha='left', va='center', color='#f39c12', fontsize=8, fontfamily='monospace')

    # --- Moteurs ---
    draw_box(ax, 62, 10, 12, 8, "Moteur G", '#e67e22')
    draw_box(ax, 80, 10, 12, 8, "Moteur D", '#e67e22')

    # --- Capteurs laser ---
    draw_box(ax, 82, 40, 16, 6, "VL53L0X x3", '#1abc9c', "Lasers I2C", fontsize=10)

    # --- MPU6050 ---
    draw_box(ax, 82, 50, 16, 6, "MPU6050", '#16a085', "IMU I2C", fontsize=10)

    # --- TCRT5000 ---
    draw_box(ax, 25, 10, 20, 7, "TCRT5000 x3", '#f39c12', "Capteurs ligne", fontsize=10)

    # --- Bouton ---
    draw_box(ax, 2, 34, 14, 6, "BOUTON", '#3498db', "START", fontsize=10)

    # --- Fils ---
    # Batterie -> LM2596
    draw_wire(ax, [(42, 88), (20, 88), (20, 78)], WIRE_COLORS['power'], "+7.2V")
    # Batterie -> L298N
    draw_wire(ax, [(58, 88), (80, 88), (80, 78)], WIRE_COLORS['power'], "+7.2V")
    # LM2596 -> Arduino 5V
    draw_wire(ax, [(20, 70), (20, 60), (35, 60), (35, 58)], '#2ecc71', "5V")
    # L298N -> Arduino (signaux PWM)
    draw_wire(ax, [(70, 70), (45, 65), (28, 58)], '#e67e22', "ENA/IN1-4/ENB")
    # L298N -> Moteurs
    draw_wire(ax, [(74, 70), (68, 18)], WIRE_COLORS['motor'], "OUT1/2")
    draw_wire(ax, [(86, 70), (86, 18)], WIRE_COLORS['motor'], "OUT3/4")
    # Arduino -> Lasers (I2C)
    draw_wire(ax, [(75, 46), (82, 43)], '#2ecc71', "SDA/SCL")
    # Arduino -> Lasers (XSHUT)
    draw_wire(ax, [(75, 40), (82, 41)], '#1abc9c')
    # Arduino -> MPU6050 (I2C)
    draw_wire(ax, [(75, 48), (82, 53)], '#2ecc71', "I2C")
    # Arduino -> TCRT5000
    draw_wire(ax, [(35, 28), (35, 17)], '#f39c12', "A0/A1/A2")
    # Arduino -> Bouton
    draw_wire(ax, [(25, 37), (16, 37)], '#3498db', "Pin 2")

    # GND commun
    ax.plot([5, 95], [4, 4], color=WIRE_COLORS['gnd'], linewidth=5, zorder=1, alpha=0.7)
    for gx in [20, 35, 50, 68, 80, 86, 90]:
        ax.plot([gx, gx], [4, 10 if gx in [68, 86] else 7], color=WIRE_COLORS['gnd'], linewidth=2, zorder=2)
    ax.text(50, 1, "GND COMMUN — tous les composants partagent cette masse",
            ha='center', color='#95a5a6', fontsize=10, fontweight='bold', fontfamily='sans-serif')

    # Legende
    ly = 96
    items = [
        (WIRE_COLORS['power'], "7.2V", 2),
        ('#2ecc71', "5V", 16),
        ('#e67e22', "Moteurs/PWM", 28),
        ('#2ecc71', "I2C", 46),
        ('#1abc9c', "Lasers XSHUT", 56),
        ('#f39c12', "Ligne", 73),
        ('#3498db', "Bouton", 83),
        (WIRE_COLORS['gnd'], "GND", 93),
    ]
    for color, label, lx in items:
        ax.plot([lx, lx+3], [ly, ly], color=color, linewidth=3)
        ax.text(lx+4, ly, label, color=TEXT_COLOR, fontsize=7, va='center', fontfamily='sans-serif')

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'schema_cablage.png'), dpi=180, facecolor=BG_COLOR,
                bbox_inches='tight', pad_inches=0.5)
    plt.close(fig)
    print("  schema_cablage.png")


# =============================================================
# DIAGRAMME 3 : Placement des capteurs (vue de dessus)
# =============================================================
def generate_capteurs():
    fig, ax = setup_fig(14, 12, "Placement des capteurs sur le robot (vue de dessus)")

    # Robot body
    robot = FancyBboxPatch((25, 20), 50, 60, boxstyle="round,pad=1",
                            facecolor='#2c3e50', edgecolor='#ecf0f1', linewidth=2)
    ax.add_patch(robot)
    ax.text(50, 5, "ARRIERE", ha='center', color='#7f8c8d', fontsize=12, fontfamily='sans-serif')
    ax.text(50, 85, "AVANT", ha='center', color='#ecf0f1', fontsize=14, fontweight='bold', fontfamily='sans-serif')

    # Roues
    for wy in [35, 65]:
        ax.add_patch(patches.Rectangle((20, wy-3), 5, 6, facecolor='#e67e22', edgecolor='white', linewidth=1))
        ax.add_patch(patches.Rectangle((75, wy-3), 5, 6, facecolor='#e67e22', edgecolor='white', linewidth=1))
    ax.text(22.5, 28, "Roue G", ha='center', color='#e67e22', fontsize=7, fontfamily='sans-serif')
    ax.text(77.5, 28, "Roue D", ha='center', color='#e67e22', fontsize=7, fontfamily='sans-serif')

    # Bille folle
    ax.add_patch(patches.Circle((50, 23), 2.5, facecolor='#7f8c8d', edgecolor='white', linewidth=1))
    ax.text(50, 17, "Bille folle", ha='center', color='#7f8c8d', fontsize=8, fontfamily='sans-serif')

    # Capteurs ligne TCRT5000
    for (cx, cy, label) in [(33, 77, "TCRT #1\nA0 (avant-G)"), (67, 77, "TCRT #2\nA1 (avant-D)"), (50, 25, "TCRT #3\nA2 (arriere)")]:
        ax.add_patch(patches.Rectangle((cx-3, cy-2), 6, 4, facecolor='#f39c12', edgecolor='white', linewidth=1.5, zorder=5))
        offset = 6 if cy > 50 else -6
        ax.text(cx, cy + offset, label, ha='center', va='center', color='#f39c12',
                fontsize=8, fontweight='bold', fontfamily='sans-serif',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=BG_COLOR, edgecolor='#f39c12', alpha=0.9))

    # Capteurs laser VL53L0X
    # Centre
    ax.add_patch(patches.Rectangle((47, 76), 6, 4, facecolor='#1abc9c', edgecolor='white', linewidth=1.5, zorder=5))
    # Faisceaux
    ax.annotate('', xy=(50, 95), xytext=(50, 80),
                arrowprops=dict(arrowstyle='->', color='#1abc9c', lw=2, ls='--'))
    ax.text(53, 89, "Laser #0\n(centre)", ha='left', color='#1abc9c', fontsize=8, fontweight='bold', fontfamily='sans-serif')

    # Gauche (~30 deg)
    ax.add_patch(patches.Rectangle((30, 72), 5, 3, facecolor='#1abc9c', edgecolor='white', linewidth=1.5, zorder=5))
    ax.annotate('', xy=(22, 92), xytext=(32, 75),
                arrowprops=dict(arrowstyle='->', color='#1abc9c', lw=2, ls='--'))
    ax.text(15, 92, "Laser #1\n(gauche ~30°)", ha='center', color='#1abc9c', fontsize=8, fontweight='bold', fontfamily='sans-serif')

    # Droite (~30 deg)
    ax.add_patch(patches.Rectangle((65, 72), 5, 3, facecolor='#1abc9c', edgecolor='white', linewidth=1.5, zorder=5))
    ax.annotate('', xy=(78, 92), xytext=(68, 75),
                arrowprops=dict(arrowstyle='->', color='#1abc9c', lw=2, ls='--'))
    ax.text(85, 92, "Laser #2\n(droite ~30°)", ha='center', color='#1abc9c', fontsize=8, fontweight='bold', fontfamily='sans-serif')

    # MPU6050 au centre
    ax.add_patch(patches.Rectangle((44, 48), 12, 8, facecolor='#16a085', edgecolor='white', linewidth=1.5, zorder=5))
    ax.text(50, 52, "MPU6050\n(IMU)", ha='center', va='center', color='white', fontsize=9, fontweight='bold', fontfamily='sans-serif')

    # Arduino au milieu-bas
    ax.add_patch(FancyBboxPatch((35, 33), 30, 10, boxstyle="round,pad=0.3",
                                 facecolor='#27ae60', edgecolor='white', linewidth=1.5, zorder=5))
    ax.text(50, 38, "Arduino Mega\n+ Shield", ha='center', va='center', color='white', fontsize=9, fontweight='bold', fontfamily='sans-serif')

    # Legende
    items = [
        ('#1abc9c', "VL53L0X (laser distance)", 2, 10),
        ('#f39c12', "TCRT5000 (capteur ligne)", 2, 6),
        ('#16a085', "MPU6050 (accelerometre)", 50, 10),
        ('#27ae60', "Arduino Mega", 50, 6),
        ('#e67e22', "Roues silicone", 2, 2),
    ]
    for color, label, lx, ly in items:
        ax.add_patch(patches.Rectangle((lx, ly-1), 3, 2, facecolor=color, edgecolor='white', linewidth=0.5))
        ax.text(lx + 4, ly, label, color=TEXT_COLOR, fontsize=8, va='center', fontfamily='sans-serif')

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'schema_capteurs.png'), dpi=180, facecolor=BG_COLOR,
                bbox_inches='tight', pad_inches=0.5)
    plt.close(fig)
    print("  schema_capteurs.png")


# =============================================================
# DIAGRAMME 4 : Tableau du pinout (style visuel)
# =============================================================
def generate_pinout():
    fig, ax = setup_fig(14, 10, "Pinout Arduino Mega — SumoBot")

    # Table data
    headers = ["Pin Arduino", "Branche a...", "Composant"]
    rows = [
        ["Pin 2", "Bouton START → GND", "Bouton poussoir"],
        ["Pin 5", "ENB (vitesse moteur droit)", "L298N"],
        ["Pin 6", "IN3 (sens moteur droit)", "L298N"],
        ["Pin 7", "IN4 (sens moteur droit)", "L298N"],
        ["Pin 8", "IN2 (sens moteur gauche)", "L298N"],
        ["Pin 9", "IN1 (sens moteur gauche)", "L298N"],
        ["Pin 10", "ENA (vitesse moteur gauche)", "L298N"],
        ["Pin 13", "LED etat du robot", "LED interne"],
        ["Pin 20 (SDA)", "Fil donnees I2C", "VL53L0X + MPU6050"],
        ["Pin 21 (SCL)", "Fil horloge I2C", "VL53L0X + MPU6050"],
        ["Pin 22", "XSHUT laser centre", "VL53L0X #0"],
        ["Pin 23", "XSHUT laser gauche", "VL53L0X #1"],
        ["Pin 24", "XSHUT laser droite", "VL53L0X #2"],
        ["A0", "Capteur ligne avant-gauche", "TCRT5000 #1"],
        ["A1", "Capteur ligne avant-droit", "TCRT5000 #2"],
        ["A2", "Capteur ligne arriere", "TCRT5000 #3"],
        ["5V", "Alimentation (depuis LM2596)", "Regulateur buck"],
        ["GND", "Masse commune", "Tous"],
    ]

    row_colors_map = {
        'Bouton': '#3498db',
        'L298N': '#e67e22',
        'LED': '#7f8c8d',
        'VL53L0X + MPU': '#2ecc71',
        'VL53L0X #': '#1abc9c',
        'TCRT': '#f39c12',
        'Regulateur': '#e74c3c',
        'Tous': '#2c3e50',
    }

    def get_row_color(comp):
        for key, color in row_colors_map.items():
            if key in comp:
                return color
        return '#34495e'

    n_rows = len(rows)
    row_h = 4.2
    col_widths = [18, 38, 25]
    table_x = 10
    table_y = 90 - row_h

    # Header
    x = table_x
    for i, (header, cw) in enumerate(zip(headers, col_widths)):
        ax.add_patch(patches.Rectangle((x, table_y), cw, row_h, facecolor='#2c3e50', edgecolor='#ecf0f1', linewidth=1))
        ax.text(x + cw/2, table_y + row_h/2, header, ha='center', va='center',
                color='white', fontsize=10, fontweight='bold', fontfamily='sans-serif')
        x += cw

    # Rows
    for r, row in enumerate(rows):
        y = table_y - (r + 1) * row_h
        color = get_row_color(row[2])
        x = table_x
        for i, (cell, cw) in enumerate(zip(row, col_widths)):
            bg = color if i == 0 else '#1a1a2e'
            ax.add_patch(patches.Rectangle((x, y), cw, row_h, facecolor=bg, edgecolor='#34495e',
                                           linewidth=0.8, alpha=0.85))
            ax.text(x + cw/2, y + row_h/2, cell, ha='center', va='center',
                    color='white', fontsize=8.5, fontfamily='sans-serif')
            x += cw

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'schema_pinout.png'), dpi=180, facecolor=BG_COLOR,
                bbox_inches='tight', pad_inches=0.5)
    plt.close(fig)
    print("  schema_pinout.png")


# =============================================================
# MAIN
# =============================================================
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    print("Generation des diagrammes PNG...")
    generate_alimentation()
    generate_cablage_complet()
    generate_capteurs()
    generate_pinout()
    print(f"Termine ! Fichiers dans {OUT_DIR}")
