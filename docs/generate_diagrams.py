"""
Genere les diagrammes PNG pour le guide de montage du SumoBot.
Usage: python generate_diagrams.py
Produit: schema_cablage.png, schema_alimentation.png, schema_capteurs.png, schema_pinout.png
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import os

# Style commun
BG_COLOR = '#1a1a2e'
TEXT_COLOR = '#ecf0f1'

COL = {
    'power': '#e74c3c',
    'gnd': '#636e72',
    'v5': '#2ecc71',
    'pwm': '#e67e22',
    'i2c': '#2ecc71',
    'motor': '#9b59b6',
    'line': '#f39c12',
    'laser': '#1abc9c',
    'btn': '#3498db',
}


def setup_fig(width, height, title, ylim=100):
    fig, ax = plt.subplots(1, 1, figsize=(width, height), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, ylim)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, color=TEXT_COLOR, fontsize=20, fontweight='bold', pad=15,
                 fontfamily='sans-serif')
    return fig, ax


def box(ax, x, y, w, h, label, color, sub=None, fs=12):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5",
                        facecolor=color, edgecolor='white', linewidth=1.5, alpha=0.92)
    ax.add_patch(b)
    ty = y + h/2 + (1.8 if sub else 0)
    ax.text(x + w/2, ty, label, ha='center', va='center', color='white',
            fontsize=fs, fontweight='bold', fontfamily='sans-serif')
    if sub:
        ax.text(x + w/2, y + h/2 - 1.8, sub, ha='center', va='center',
                color='#bdc3c7', fontsize=fs - 3, fontfamily='sans-serif')


def wire(ax, pts, color, lw=2.5):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=color, linewidth=lw, solid_capstyle='round', zorder=2)
    for p in pts:
        ax.plot(p[0], p[1], 'o', color=color, markersize=3.5, zorder=3)


def wire_label(ax, x, y, text, color, fs=9, ha='center', va='center'):
    ax.text(x, y, text, ha=ha, va=va, color=color, fontsize=fs, fontweight='bold',
            fontfamily='sans-serif',
            bbox=dict(boxstyle='round,pad=0.25', facecolor=BG_COLOR, edgecolor=color,
                      alpha=0.9, linewidth=1))


def legend_line(ax, x, y, color, label, fs=9):
    ax.plot([x, x + 4], [y, y], color=color, linewidth=3.5, solid_capstyle='round')
    ax.text(x + 5.5, y, label, color=TEXT_COLOR, fontsize=fs, va='center', fontfamily='sans-serif')


# =============================================================
# DIAGRAMME 1 : Schema d'alimentation
# =============================================================
def generate_alimentation():
    fig, ax = setup_fig(14, 11, "Schema d'alimentation", ylim=105)

    # Legende en haut — bien espacee
    ly = 100
    legend_line(ax, 2, ly, COL['power'], "7.2V (batterie)")
    legend_line(ax, 30, ly, COL['v5'], "5V (regulee)")
    legend_line(ax, 55, ly, COL['motor'], "Vers moteurs")
    legend_line(ax, 80, ly, COL['gnd'], "GND (masse)")

    # Batterie
    box(ax, 33, 80, 34, 12, "BATTERIE", '#c0392b', "NiMH 7.2V", fs=15)

    # LM2596
    box(ax, 8, 50, 28, 12, "LM2596", '#2980b9', "Convertisseur 7.2V → 5V", fs=13)

    # L298N
    box(ax, 64, 50, 28, 12, "L298N", '#8e44ad', "Pont H (commande moteurs)", fs=13)

    # Arduino
    box(ax, 22, 15, 34, 14, "ARDUINO MEGA", '#27ae60', "Alimente via pin 5V", fs=14)

    # Moteurs
    box(ax, 65, 15, 13, 10, "Moteur G", '#e67e22', fs=11)
    box(ax, 83, 15, 13, 10, "Moteur D", '#e67e22', fs=11)

    # --- Fils ---
    # Batterie -> LM2596
    wire(ax, [(38, 80), (38, 72), (22, 72), (22, 62)], COL['power'])
    wire_label(ax, 28, 74, "+7.2V", COL['power'])

    # Batterie -> L298N
    wire(ax, [(62, 80), (62, 72), (78, 72), (78, 62)], COL['power'])
    wire_label(ax, 72, 74, "+7.2V", COL['power'])

    # LM2596 -> Arduino
    wire(ax, [(22, 50), (22, 40), (39, 40), (39, 29)], COL['v5'])
    wire_label(ax, 30, 42, "5V", COL['v5'])

    # L298N -> Moteur G
    wire(ax, [(72, 50), (71.5, 25)], COL['motor'])
    wire_label(ax, 66, 38, "OUT1/2", COL['motor'], fs=8)

    # L298N -> Moteur D
    wire(ax, [(86, 50), (89.5, 25)], COL['motor'])
    wire_label(ax, 93, 38, "OUT3/4", COL['motor'], fs=8)

    # GND commun (barre epaisse en bas)
    ax.add_patch(FancyBboxPatch((8, 2), 84, 4, boxstyle="round,pad=0.3",
                                 facecolor='#2d3436', edgecolor=COL['gnd'], linewidth=2, alpha=0.8))
    ax.text(50, 4, "GND COMMUN — masse partagee par tous les composants",
            ha='center', va='center', color='#dfe6e9', fontsize=10, fontweight='bold',
            fontfamily='sans-serif')
    # Fils GND vers la barre
    for gx in [22, 39, 78, 71.5, 89.5]:
        wire(ax, [(gx, 6), (gx, 15 if gx in [22, 39] else 15)], COL['gnd'], lw=1.5)

    # Avertissement
    ax.text(50, 46, "JAMAIS brancher 7.2V directement sur le pin 5V de l'Arduino !",
            ha='center', va='center', color='#e74c3c', fontsize=11, fontweight='bold',
            fontfamily='sans-serif',
            bbox=dict(boxstyle='round,pad=0.6', facecolor='#1a1a2e', edgecolor='#e74c3c', linewidth=2.5))

    fig.savefig(os.path.join(OUT_DIR, 'schema_alimentation.png'), dpi=150, facecolor=BG_COLOR,
                bbox_inches='tight', pad_inches=0.4)
    plt.close(fig)
    print("  schema_alimentation.png")


# =============================================================
# DIAGRAMME 2 : Schema de cablage complet
# =============================================================
def generate_cablage_complet():
    fig, ax = setup_fig(20, 16, "Schema de cablage complet du SumoBot", ylim=110)

    # --- Legende en haut, 2 lignes ---
    ly1, ly2 = 106, 102
    legend_line(ax, 2, ly1, COL['power'], "7.2V (batterie)")
    legend_line(ax, 30, ly1, COL['v5'], "5V (regulee)")
    legend_line(ax, 55, ly1, COL['pwm'], "Signaux moteurs (PWM)")
    legend_line(ax, 2, ly2, COL['i2c'], "I2C (SDA/SCL)")
    legend_line(ax, 30, ly2, COL['laser'], "XSHUT (lasers)")
    legend_line(ax, 55, ly2, COL['line'], "Capteurs de ligne")
    legend_line(ax, 80, ly2, COL['btn'], "Bouton START")
    legend_line(ax, 80, ly1, COL['gnd'], "GND (masse)")

    # --- Batterie ---
    box(ax, 38, 88, 24, 10, "BATTERIE", '#c0392b', "NiMH 7.2V", fs=14)

    # --- LM2596 ---
    box(ax, 5, 68, 22, 10, "LM2596", '#2980b9', "7.2V → 5V", fs=12)

    # --- L298N ---
    box(ax, 73, 68, 22, 10, "L298N", '#8e44ad', "Pont H", fs=12)

    # --- Arduino Mega (grand bloc central) ---
    mega = FancyBboxPatch((22, 30), 56, 28, boxstyle="round,pad=0.8",
                           facecolor='#1e3a2f', edgecolor='#2ecc71', linewidth=2.5, alpha=0.95)
    ax.add_patch(mega)
    ax.text(50, 54, "ARDUINO MEGA 2560 + Shield Sensor", ha='center', va='center',
            color='#2ecc71', fontsize=14, fontweight='bold', fontfamily='sans-serif')

    # Pins gauche (moteurs)
    pins_l = [
        ("Pin 10  ENA", 48),
        ("Pin 9   IN1", 45.5),
        ("Pin 8   IN2", 43),
        ("Pin 7   IN4", 40.5),
        ("Pin 6   IN3", 38),
        ("Pin 5   ENB", 35.5),
    ]
    for label, y in pins_l:
        ax.text(24, y, label, ha='left', va='center', color=COL['pwm'],
                fontsize=8, fontfamily='monospace', fontweight='bold')

    # Pins droite (capteurs)
    pins_r = [
        ("SDA    Pin 20", 48, COL['i2c']),
        ("SCL    Pin 21", 45.5, COL['i2c']),
        ("XSHUT0 Pin 22", 43, COL['laser']),
        ("XSHUT1 Pin 23", 40.5, COL['laser']),
        ("XSHUT2 Pin 24", 38, COL['laser']),
        ("BTN    Pin 2 ", 35.5, COL['btn']),
    ]
    for label, y, c in pins_r:
        ax.text(57, y, label, ha='left', va='center', color=c,
                fontsize=8, fontfamily='monospace', fontweight='bold')

    # Pins bas (ligne)
    ax.text(50, 32, "A0 (avant-G)      A1 (avant-D)      A2 (arriere)",
            ha='center', va='center', color=COL['line'], fontsize=8.5,
            fontfamily='monospace', fontweight='bold')

    # --- Composants externes ---
    # Moteurs
    box(ax, 60, 6, 14, 9, "Moteur G", '#e67e22', fs=11)
    box(ax, 82, 6, 14, 9, "Moteur D", '#e67e22', fs=11)

    # Capteurs laser
    box(ax, 82, 42, 16, 8, "VL53L0X x3", '#1abc9c', "Lasers", fs=11)

    # MPU6050
    box(ax, 82, 53, 16, 8, "MPU6050", '#16a085', "IMU", fs=11)

    # TCRT5000
    box(ax, 20, 6, 22, 9, "TCRT5000 x3", COL['line'], "Capteurs ligne", fs=11)

    # Bouton
    box(ax, 1, 36, 14, 8, "BOUTON", COL['btn'], "START", fs=11)

    # --- Fils (bien separes) ---

    # Batterie -> LM2596
    wire(ax, [(40, 88), (16, 88), (16, 78)], COL['power'])
    wire_label(ax, 26, 90, "+7.2V", COL['power'], fs=8)

    # Batterie -> L298N
    wire(ax, [(60, 88), (84, 88), (84, 78)], COL['power'])
    wire_label(ax, 74, 90, "+7.2V", COL['power'], fs=8)

    # LM2596 -> Arduino 5V
    wire(ax, [(16, 68), (16, 62), (30, 62), (30, 58)], COL['v5'])
    wire_label(ax, 22, 64, "5V", COL['v5'], fs=9)

    # L298N -> Arduino (signaux PWM) — courbe haute pour eviter les blocs
    wire(ax, [(73, 74), (55, 65), (24, 58)], COL['pwm'])
    wire_label(ax, 42, 67, "ENA / IN1-4 / ENB", COL['pwm'], fs=8)

    # L298N -> Moteur G
    wire(ax, [(78, 68), (67, 15)], COL['motor'])
    wire_label(ax, 68, 30, "OUT1/2", COL['motor'], fs=8, ha='right')

    # L298N -> Moteur D
    wire(ax, [(90, 68), (89, 15)], COL['motor'])
    wire_label(ax, 95, 30, "OUT3/4", COL['motor'], fs=8, ha='left')

    # Arduino -> MPU6050 (I2C) — sort en haut a droite
    wire(ax, [(78, 50), (82, 57)], COL['i2c'])
    wire_label(ax, 80, 54, "SDA/SCL", COL['i2c'], fs=8)

    # Arduino -> VL53L0X (I2C) — meme bus
    wire(ax, [(78, 48), (82, 47)], COL['i2c'])

    # Arduino -> VL53L0X (XSHUT) — sort a droite plus bas
    wire(ax, [(78, 41), (82, 43)], COL['laser'])
    wire_label(ax, 81, 38, "XSHUT", COL['laser'], fs=8)

    # Arduino -> TCRT5000
    wire(ax, [(31, 30), (31, 15)], COL['line'])
    wire_label(ax, 36, 22, "A0 / A1 / A2", COL['line'], fs=8)

    # Arduino -> Bouton
    wire(ax, [(22, 40), (15, 40)], COL['btn'])
    wire_label(ax, 18, 44, "Pin 2", COL['btn'], fs=8)

    # GND commun (barre epaisse en bas)
    ax.add_patch(FancyBboxPatch((5, 0), 92, 3.5, boxstyle="round,pad=0.2",
                                 facecolor='#2d3436', edgecolor=COL['gnd'], linewidth=2, alpha=0.8))
    ax.text(50, 1.7, "GND COMMUN — tous les composants partagent cette masse",
            ha='center', va='center', color='#dfe6e9', fontsize=10, fontweight='bold',
            fontfamily='sans-serif')

    fig.savefig(os.path.join(OUT_DIR, 'schema_cablage.png'), dpi=150, facecolor=BG_COLOR,
                bbox_inches='tight', pad_inches=0.4)
    plt.close(fig)
    print("  schema_cablage.png")


# =============================================================
# DIAGRAMME 3 : Placement des capteurs (vue de dessus)
# =============================================================
def generate_capteurs():
    fig, ax = setup_fig(14, 14, "Placement des capteurs sur le robot (vue de dessus)", ylim=110)

    # Legende en haut pour degager le bas
    ly = 105
    items_leg = [
        ('#1abc9c', "VL53L0X (laser)", 2),
        ('#f39c12', "TCRT5000 (ligne)", 28),
        ('#16a085', "MPU6050 (IMU)", 55),
        ('#27ae60', "Arduino Mega", 78),
    ]
    for c, lab, lx in items_leg:
        ax.add_patch(patches.Rectangle((lx, ly - 1), 3.5, 2.5, facecolor=c, edgecolor='white', linewidth=0.5))
        ax.text(lx + 5, ly + 0.2, lab, color=TEXT_COLOR, fontsize=9, va='center', fontfamily='sans-serif')

    ly2 = 100
    ax.add_patch(patches.Rectangle((2, ly2 - 1), 3.5, 2.5, facecolor='#74b9ff', edgecolor='white', linewidth=0.5))
    ax.text(7, ly2 + 0.2, "Roues silicone (x2)", color=TEXT_COLOR, fontsize=9, va='center', fontfamily='sans-serif')
    ax.add_patch(patches.Circle((32, ly2 + 0.2), 1.5, facecolor='#7f8c8d', edgecolor='white', linewidth=0.5))
    ax.text(35, ly2 + 0.2, "Bille folle (appui arriere)", color=TEXT_COLOR, fontsize=9, va='center', fontfamily='sans-serif')

    # Labels direction
    ax.text(50, 93, "AVANT", ha='center', color='#ecf0f1', fontsize=16, fontweight='bold', fontfamily='sans-serif')
    ax.text(50, 13, "ARRIERE", ha='center', color='#7f8c8d', fontsize=14, fontfamily='sans-serif')

    # Robot body
    robot = FancyBboxPatch((22, 20), 56, 68, boxstyle="round,pad=1.2",
                            facecolor='#2c3e50', edgecolor='#ecf0f1', linewidth=2.5)
    ax.add_patch(robot)

    # Roues (2 seulement : une gauche, une droite, au milieu du chassis)
    WHEEL_COLOR = '#74b9ff'
    ax.add_patch(patches.Rectangle((17, 50), 6, 10, facecolor=WHEEL_COLOR, edgecolor='white', linewidth=1.2))
    ax.add_patch(patches.Rectangle((77, 50), 6, 10, facecolor=WHEEL_COLOR, edgecolor='white', linewidth=1.2))

    ax.text(20, 46, "Roue G", ha='center', color=WHEEL_COLOR, fontsize=9, fontweight='bold', fontfamily='sans-serif')
    ax.text(80, 46, "Roue D", ha='center', color=WHEEL_COLOR, fontsize=9, fontweight='bold', fontfamily='sans-serif')

    # Bille folle
    ax.add_patch(patches.Circle((50, 25), 3, facecolor='#7f8c8d', edgecolor='white', linewidth=1.2))
    ax.text(60, 25, "Bille folle", ha='left', color='#b2bec3', fontsize=9, fontfamily='sans-serif')

    # === Capteurs ligne TCRT5000 ===
    # Avant-gauche
    ax.add_patch(patches.Rectangle((32, 80), 7, 5, facecolor='#f39c12', edgecolor='white', linewidth=1.5, zorder=5))
    ax.text(35.5, 82.5, "#1", ha='center', va='center', color='white', fontsize=9, fontweight='bold', zorder=6)
    ax.text(35.5, 88, "TCRT #1 — A0", ha='center', va='bottom', color='#f39c12',
            fontsize=9, fontweight='bold', fontfamily='sans-serif',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=BG_COLOR, edgecolor='#f39c12', alpha=0.9))

    # Avant-droit
    ax.add_patch(patches.Rectangle((61, 80), 7, 5, facecolor='#f39c12', edgecolor='white', linewidth=1.5, zorder=5))
    ax.text(64.5, 82.5, "#2", ha='center', va='center', color='white', fontsize=9, fontweight='bold', zorder=6)
    ax.text(64.5, 88, "TCRT #2 — A1", ha='center', va='bottom', color='#f39c12',
            fontsize=9, fontweight='bold', fontfamily='sans-serif',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=BG_COLOR, edgecolor='#f39c12', alpha=0.9))

    # Arriere
    ax.add_patch(patches.Rectangle((46.5, 22), 7, 5, facecolor='#f39c12', edgecolor='white', linewidth=1.5, zorder=5))
    ax.text(50, 24.5, "#3", ha='center', va='center', color='white', fontsize=9, fontweight='bold', zorder=6)
    ax.text(37, 19, "TCRT #3\nA2 (arriere)", ha='center', va='top', color='#f39c12',
            fontsize=9, fontweight='bold', fontfamily='sans-serif',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=BG_COLOR, edgecolor='#f39c12', alpha=0.9))

    # === Capteurs laser VL53L0X ===
    # Centre
    ax.add_patch(patches.Rectangle((47, 82), 6, 4, facecolor='#1abc9c', edgecolor='white', linewidth=1.5, zorder=5))
    ax.annotate('', xy=(50, 96), xytext=(50, 86),
                arrowprops=dict(arrowstyle='->', color='#1abc9c', lw=2.5, ls='--'))
    ax.text(55, 92, "Laser #0\n(centre)", ha='left', color='#1abc9c', fontsize=9, fontweight='bold',
            fontfamily='sans-serif')

    # Gauche
    ax.add_patch(patches.Rectangle((26, 76), 5, 4, facecolor='#1abc9c', edgecolor='white', linewidth=1.5, zorder=5))
    ax.annotate('', xy=(15, 95), xytext=(28, 80),
                arrowprops=dict(arrowstyle='->', color='#1abc9c', lw=2.5, ls='--'))
    ax.text(5, 96, "Laser #1\n(gauche ~30°)", ha='center', color='#1abc9c', fontsize=9, fontweight='bold',
            fontfamily='sans-serif')

    # Droite
    ax.add_patch(patches.Rectangle((69, 76), 5, 4, facecolor='#1abc9c', edgecolor='white', linewidth=1.5, zorder=5))
    ax.annotate('', xy=(85, 95), xytext=(72, 80),
                arrowprops=dict(arrowstyle='->', color='#1abc9c', lw=2.5, ls='--'))
    ax.text(95, 96, "Laser #2\n(droite ~30°)", ha='center', color='#1abc9c', fontsize=9, fontweight='bold',
            fontfamily='sans-serif')

    # === MPU6050 au centre ===
    ax.add_patch(patches.Rectangle((43, 54), 14, 10, facecolor='#16a085', edgecolor='white', linewidth=1.5, zorder=5))
    ax.text(50, 59, "MPU6050\n(IMU)", ha='center', va='center', color='white', fontsize=10,
            fontweight='bold', fontfamily='sans-serif')

    # === Arduino au milieu-bas ===
    ax.add_patch(FancyBboxPatch((33, 38), 34, 12, boxstyle="round,pad=0.4",
                                 facecolor='#27ae60', edgecolor='white', linewidth=1.5, zorder=5))
    ax.text(50, 44, "Arduino Mega\n+ Shield", ha='center', va='center', color='white', fontsize=11,
            fontweight='bold', fontfamily='sans-serif')

    fig.savefig(os.path.join(OUT_DIR, 'schema_capteurs.png'), dpi=150, facecolor=BG_COLOR,
                bbox_inches='tight', pad_inches=0.4)
    plt.close(fig)
    print("  schema_capteurs.png")


# =============================================================
# DIAGRAMME 4 : Tableau du pinout
# =============================================================
def generate_pinout():
    fig, ax = setup_fig(14, 12, "Pinout Arduino Mega — SumoBot", ylim=110)

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

    color_map = {
        'Bouton': '#3498db', 'L298N': '#e67e22', 'LED': '#7f8c8d',
        'VL53L0X + MPU': '#2ecc71', 'VL53L0X #': '#1abc9c',
        'TCRT': '#f39c12', 'Regulateur': '#e74c3c', 'Tous': '#636e72',
    }

    def row_color(comp):
        for key, c in color_map.items():
            if key in comp:
                return c
        return '#34495e'

    row_h = 4.8
    col_w = [20, 38, 24]
    tx = 9
    ty = 100 - row_h  # top of header

    # Header
    x = tx
    for header, cw in zip(headers, col_w):
        ax.add_patch(patches.Rectangle((x, ty), cw, row_h, facecolor='#2c3e50', edgecolor='#ecf0f1', linewidth=1.2))
        ax.text(x + cw/2, ty + row_h/2, header, ha='center', va='center',
                color='white', fontsize=11, fontweight='bold', fontfamily='sans-serif')
        x += cw

    # Data rows
    for r, row in enumerate(rows):
        y = ty - (r + 1) * row_h
        rc = row_color(row[2])
        x = tx
        for i, (cell, cw) in enumerate(zip(row, col_w)):
            bg = rc if i == 0 else '#1a1a2e'
            ax.add_patch(patches.Rectangle((x, y), cw, row_h, facecolor=bg, edgecolor='#34495e',
                                           linewidth=0.8, alpha=0.88))
            ax.text(x + cw/2, y + row_h/2, cell, ha='center', va='center',
                    color='white', fontsize=9, fontfamily='sans-serif')
            x += cw

    fig.savefig(os.path.join(OUT_DIR, 'schema_pinout.png'), dpi=150, facecolor=BG_COLOR,
                bbox_inches='tight', pad_inches=0.4)
    plt.close(fig)
    print("  schema_pinout.png")


# =============================================================
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    print("Generation des diagrammes PNG...")
    generate_alimentation()
    generate_cablage_complet()
    generate_capteurs()
    generate_pinout()
    print(f"Termine ! Fichiers dans {OUT_DIR}")
