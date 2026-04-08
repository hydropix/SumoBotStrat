"""
Genere un fichier Fritzing .fzz pour le SumoBot.
Compatible Fritzing 0.9.3b et 1.x.

Le .fzz inclut les .fzpz communautaires (L298N) directement dans l'archive.
Les composants core (Arduino Mega, DC motors, bouton) sont references via les
paths standards de Fritzing.

Usage: python generate_fritzing.py
Produit: sumobot.fzz
"""

import zipfile
import os
import urllib.request
import tempfile

# ==================== CONNECTOR MAPS ====================

# Arduino Mega 2560 Rev3 (from fritzing-parts/obsolete/Arduino_MEGA_2560-Rev3.fzp)
MEGA_CONN = {
    'A0': 'connector8', 'A1': 'connector9', 'A2': 'connector10',
    'D2': 'connector264', 'D5': 'connector267', 'D6': 'connector268',
    'D7': 'connector269', 'D8': 'connector243', 'D9': 'connector242',
    'D10': 'connector241', 'D13': 'connector238',
    'D20_SDA': 'connector47', 'D21_SCL': 'connector46',
    'D22': 'connector345', 'D23': 'connector346', 'D24': 'connector347',
    '5V': 'connector258', '5V_2': 'connector343', '5V_3': 'connector344',
    'GND': 'connector259', 'GND_2': 'connector260',
    'GND_3': 'connector377', 'GND_4': 'connector378',
    'VIN': 'connector261',
}

# L298N H-Bridge (from yohendry/arduino_L298N .fzpz)
L298N_CONN = {
    '12V': 'connector1', 'GND': 'connector2', '5V': 'connector3',
    'ENA': 'connector4', 'IN1': 'connector5', 'IN2': 'connector6',
    'IN3': 'connector7', 'IN4': 'connector8', 'ENB': 'connector9',
    'M1_01': 'connector10', 'M1_02': 'connector11',
    'M2_01': 'connector13', 'M2_02': 'connector14',
}

WIRE_RED = '#cc1414'
WIRE_BLACK = '#404040'
WIRE_GREEN = '#25b22b'
WIRE_BLUE = '#418dd9'
WIRE_ORANGE = '#ef6100'
WIRE_YELLOW = '#ffe000'
WIRE_PURPLE = '#8c3ba0'
WIRE_TEAL = '#1abc9c'


class FzBuilder:
    """Builds a Fritzing .fz XML file."""

    def __init__(self):
        self._idx = 1000
        self._instances = []

    def _next(self):
        self._idx += 1
        return self._idx

    def add_part(self, module_id, path, title, x, y, z=2.5, props=None, layer='breadboard'):
        mi = self._next()
        props_xml = ''
        if props:
            for k, v in props.items():
                props_xml += f'            <property name="{k}" value="{v}"/>\n'
        self._instances.append(f'''\
        <instance moduleIdRef="{module_id}" modelIndex="{mi}" path="{path}">
{props_xml}            <title>{title}</title>
            <views>
                <breadboardView layer="{layer}">
                    <geometry z="{z}" x="{x}" y="{y}"/>
                </breadboardView>
                <schematicView layer="schematic">
                    <geometry z="{z + 3}" x="{x + 400}" y="{y}"/>
                </schematicView>
                <pcbView layer="copper0">
                    <geometry z="{z + 5}" x="{x}" y="{y + 400}"/>
                </pcbView>
            </views>
        </instance>''')
        return mi

    def add_wire(self, from_mi, from_conn, to_mi, to_conn, color=WIRE_BLUE,
                 x=0, y=0, dx=100, dy=0):
        mi = self._next()
        self._instances.append(f'''\
        <instance moduleIdRef="WireModuleID" modelIndex="{mi}" path=":/resources/parts/core/wire.fzp">
            <title>Wire{mi}</title>
            <views>
                <breadboardView layer="breadboardWire">
                    <geometry z="3.5" x="{x}" y="{y}" x1="0" y1="0" x2="{dx}" y2="{dy}" wireFlags="64"/>
                    <wireExtras mils="22.2222" color="{color}" opacity="1" banded="0"/>
                    <connectors>
                        <connector connectorId="connector0" layer="breadboardWire">
                            <geometry x="0" y="0"/>
                            <connects>
                                <connect connectorId="{from_conn}" modelIndex="{from_mi}" layer="breadboard"/>
                            </connects>
                        </connector>
                        <connector connectorId="connector1" layer="breadboardWire">
                            <geometry x="0" y="0"/>
                            <connects>
                                <connect connectorId="{to_conn}" modelIndex="{to_mi}" layer="breadboard"/>
                            </connects>
                        </connector>
                    </connectors>
                </breadboardView>
                <pcbView layer="copper1trace">
                    <geometry z="9.5" x="{x}" y="{y}" x1="0" y1="0" x2="{dx}" y2="{dy}" wireFlags="64"/>
                    <wireExtras mils="11.1111" color="#f2c600" opacity="1" banded="0"/>
                    <connectors>
                        <connector connectorId="connector0" layer="copper1trace">
                            <geometry x="0" y="0"/>
                            <connects>
                                <connect connectorId="{from_conn}" modelIndex="{from_mi}" layer="copper0"/>
                            </connects>
                        </connector>
                        <connector connectorId="connector1" layer="copper1trace">
                            <geometry x="0" y="0"/>
                            <connects>
                                <connect connectorId="{to_conn}" modelIndex="{to_mi}" layer="copper0"/>
                            </connects>
                        </connector>
                    </connectors>
                </pcbView>
                <schematicView layer="schematicTrace">
                    <geometry z="5.5" x="{x}" y="{y}" x1="0" y1="0" x2="{dx}" y2="{dy}" wireFlags="64"/>
                    <wireExtras mils="9.7222" color="#404040" opacity="1" banded="0"/>
                    <connectors>
                        <connector connectorId="connector0" layer="schematicTrace">
                            <geometry x="0" y="0"/>
                            <connects>
                                <connect connectorId="{from_conn}" modelIndex="{from_mi}" layer="schematic"/>
                            </connects>
                        </connector>
                        <connector connectorId="connector1" layer="schematicTrace">
                            <geometry x="0" y="0"/>
                            <connects>
                                <connect connectorId="{to_conn}" modelIndex="{to_mi}" layer="schematic"/>
                            </connects>
                        </connector>
                    </connectors>
                </schematicView>
            </views>
        </instance>''')
        return mi

    def add_note(self, x, y, text, w=250, h=80):
        mi = self._next()
        self._instances.append(f'''\
        <instance moduleIdRef="NoteModuleID" modelIndex="{mi}" path=":/resources/parts/core/note.fzp">
            <title>Note{mi}</title>
            <text>{text}</text>
            <views>
                <breadboardView layer="breadboardNote">
                    <geometry z="6.5" x="{x}" y="{y}" width="{w}" height="{h}"/>
                </breadboardView>
            </views>
        </instance>''')

    def build(self):
        instances = '\n'.join(self._instances)
        return f'''\
<?xml version="1.0" encoding="UTF-8"?>
<module fritzingVersion="0.9.3b" icon=".png">
    <boards>
        <board moduleId="TwoLayerRectanglePCBModuleID" title="Rectangular PCB - Resizable" instance="PCB1" width="16.9333cm" height="5.64444cm"/>
    </boards>
    <views>
        <view name="breadboardView" backgroundColor="#ffffff" gridSize="0.1in" showGrid="0" alignToGrid="0" viewFromBelow="0"/>
        <view name="schematicView" backgroundColor="#ffffff" gridSize="2.5mm" showGrid="1" alignToGrid="0" viewFromBelow="0"/>
        <view name="pcbView" backgroundColor="#333333" gridSize="0.1in" showGrid="1" alignToGrid="1" viewFromBelow="0" GPG_Keepout="" autorouteViaHoleSize="" autorouteTraceWidth="24" autorouteViaRingThickness="" DRC_Keepout=""/>
    </views>
    <instances>
        <instance moduleIdRef="TwoLayerRectanglePCBModuleID" modelIndex="999" path=":/resources/parts/core/rectangle_pcb_two_layers.fzp">
            <property name="layers" value="2"/>
            <property name="width" value="169.333333"/>
            <property name="height" value="56.4444444"/>
            <title>PCB1</title>
            <views>
                <breadboardView layer="">
                    <geometry z="0.5" x="0" y="0"/>
                </breadboardView>
                <pcbView layer="board">
                    <geometry z="1.5" x="50" y="10"/>
                </pcbView>
                <schematicView layer="">
                    <geometry z="0.5" x="0" y="0"/>
                </schematicView>
            </views>
        </instance>
{instances}
    </instances>
</module>'''


def build_sketch():
    b = FzBuilder()

    # ==================== COMPOSANTS ====================

    # Arduino Mega 2560 (core part)
    mega = b.add_part(
        "Arduino_MEGA_2560-Rev3",
        ":/resources/parts/core/Arduino_MEGA_2560-Rev3.fzp",
        "Arduino Mega 2560", x=250, y=50, z=1.5, layer='breadboard')

    # L298N (community part — included in .fzz)
    l298n = b.add_part(
        "Ponte-H L298N_dc34ee980426c09a6ce219f055923b75_2",
        "part.Ponte-H L298N_dc34ee980426c09a6ce219f055923b75_2.fzp",
        "L298N (Pont H)", x=50, y=50, z=2.5, layer='breadboard')

    # DC Motors (core)
    mot_g = b.add_part("1000FADF10011leg", ":/resources/parts/core/dc_motor.fzp",
                        "Moteur Gauche", x=30, y=300, z=2.5)
    mot_d = b.add_part("1000FADF10011leg", ":/resources/parts/core/dc_motor.fzp",
                        "Moteur Droit", x=130, y=300, z=2.5)

    # Batterie 9V (proxy pour NiMH 7.2V)
    batt = b.add_part("77c36646df552e9fe72f360837f556ccleg",
                       ":/resources/parts/core/Battery block 9V.fzp",
                       "Batterie NiMH 7.5V", x=0, y=150, z=2.5,
                       props={"voltage": "7.5V"})

    # Bouton START (core pushbutton)
    btn = b.add_part("20A9BBEE34_ST",
                      ":/resources/parts/core/pushbutton_4_horizontal.fzp",
                      "Bouton START", x=600, y=30, z=2.5)

    # Mystery part 3 pins pour le LM2596 Buck (Vin, Vout, GND)
    buck = b.add_part("mystery_part_sip_3_100mil",
                       ":/resources/parts/core/mystery_part_3.fzp",
                       "LM2596 Buck", x=0, y=50, z=2.5,
                       props={"chip label": "LM2596", "pins": "3"})

    # ==================== FILS ====================

    W = b.add_wire  # shortcut

    # --- Alimentation ---
    # Battery: connector0 = "-" (GND), connector1 = "+" (VCC)
    W(batt, 'connector1', buck, 'connector0', WIRE_RED)           # Batt+ → Buck Vin
    W(batt, 'connector1', l298n, L298N_CONN['12V'], WIRE_RED)     # Batt+ → L298N 12V
    W(buck, 'connector1', mega, MEGA_CONN['5V'], WIRE_GREEN)      # Buck 5V → Arduino 5V
    W(batt, 'connector0', mega, MEGA_CONN['GND'], WIRE_BLACK)     # Batt- → Arduino GND
    W(batt, 'connector0', l298n, L298N_CONN['GND'], WIRE_BLACK)   # Batt- → L298N GND

    # --- L298N → Arduino (controle moteurs) ---
    W(mega, MEGA_CONN['D10'], l298n, L298N_CONN['ENA'], WIRE_ORANGE)
    W(mega, MEGA_CONN['D9'],  l298n, L298N_CONN['IN1'], WIRE_ORANGE)
    W(mega, MEGA_CONN['D8'],  l298n, L298N_CONN['IN2'], WIRE_ORANGE)
    W(mega, MEGA_CONN['D6'],  l298n, L298N_CONN['IN3'], WIRE_ORANGE)
    W(mega, MEGA_CONN['D7'],  l298n, L298N_CONN['IN4'], WIRE_ORANGE)
    W(mega, MEGA_CONN['D5'],  l298n, L298N_CONN['ENB'], WIRE_ORANGE)

    # --- L298N → Moteurs ---
    W(l298n, L298N_CONN['M1_01'], mot_g, 'connector0', WIRE_PURPLE)
    W(l298n, L298N_CONN['M1_02'], mot_g, 'connector1', WIRE_PURPLE)
    W(l298n, L298N_CONN['M2_01'], mot_d, 'connector0', WIRE_PURPLE)
    W(l298n, L298N_CONN['M2_02'], mot_d, 'connector1', WIRE_PURPLE)

    # --- Bouton START → Arduino ---
    W(btn, 'connector0', mega, MEGA_CONN['D2'], WIRE_BLUE)       # Signal
    W(btn, 'connector1', mega, MEGA_CONN['GND_2'], WIRE_BLACK)   # GND

    # ==================== NOTES ====================

    b.add_note(0, -30,
        "SUMOBOT — Schema de cablage. "
        "Ajouter manuellement: VL53L0X x3, TCRT5000 x3, MPU6050 (importer les .fzpz).",
        w=700, h=30)

    b.add_note(500, 100,
        "CAPTEURS A AJOUTER:\n"
        "- 3x VL53L0X: SDA→Pin20, SCL→Pin21, XSHUT→Pin22/23/24\n"
        "- 3x TCRT5000: Signal→A0/A1/A2, VCC→5V, GND\n"
        "- 1x MPU6050: SDA→Pin20, SCL→Pin21, AD0→GND",
        w=350, h=100)

    b.add_note(0, 30,
        "LM2596 Buck: pin1=Vin(7.5V), pin2=Vout(5V), pin3=GND",
        w=300, h=25)

    return b.build()


def download_l298n_fzpz(dest_dir):
    """Download L298N .fzpz and extract files for inclusion in .fzz."""
    url = "https://github.com/yohendry/arduino_L298N/raw/master/H-Bridge%20with%20L298N.fzpz"
    fzpz_path = os.path.join(dest_dir, 'l298n.fzpz')
    try:
        print("  Telechargement du L298N .fzpz...")
        urllib.request.urlretrieve(url, fzpz_path)
        return fzpz_path
    except Exception as e:
        print(f"  Impossible de telecharger le L298N: {e}")
        return None


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    fzz_path = os.path.join(out_dir, 'sumobot.fzz')

    print("Generation du fichier Fritzing sumobot.fzz...")

    fz_xml = build_sketch()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download L298N part
        l298n_fzpz = download_l298n_fzpz(tmpdir)

        with zipfile.ZipFile(fzz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Main sketch file
            zf.writestr('sumobot.fz', fz_xml)

            # Include L298N part files in the .fzz
            if l298n_fzpz and os.path.exists(l298n_fzpz):
                with zipfile.ZipFile(l298n_fzpz, 'r') as pz:
                    for name in pz.namelist():
                        data = pz.read(name)
                        zf.writestr(name, data)
                print("  L298N inclus dans le .fzz")

    print(f"\nFichier genere: {fzz_path}")
    print()
    print("Instructions:")
    print("  1. Ouvrir sumobot.fzz dans Fritzing")
    print("  2. L'Arduino Mega et le L298N devraient apparaitre correctement")
    print("  3. Les pin headers sont des placeholders — les remplacer par les vrais:")
    print("     - VL53L0X: importer depuis github.com/adafruit/Fritzing-Library")
    print("     - MPU6050: chercher 'GY-521 fritzing part'")
    print("     - TCRT5000: chercher 'TCRT5000 fritzing part'")
    print("     - LM2596: chercher 'LM2596 fritzing part'")
    print("  4. Repositionner les composants et fils dans la vue breadboard")


if __name__ == '__main__':
    main()
