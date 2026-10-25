# Station North SNfetchPLAYER - Local Python Library Directory (pylib)

Dieses Verzeichnis dient der Bereitstellung systemspezifischer oder zusätzlicher
Python-Bibliotheken für Handheld-Custom-Firmwares (muOS, ROCKNIX, ArkOS, AmberELEC, Knulli).

## Funktionsweise in SNfetchPLAYER.sh:
Das Startskript SNfetchPLAYER.sh bindet diesen Ordner beim Start dynamisch an den Anfang
des $PYTHONPATH ein:
    export PYTHONPATH="$GAMEDIR/pylib:$PYTHONPATH"

## Externe Abhängigkeiten im Überblick:
1. Pygame:
   - Wird direkt über die offizielle PortMaster-Laufzeit (python_3.11.squashfs)
     bereitgestellt und geladen.
2. Gamepad & Input:
   - SNfetchPLAYER nutzt den integrierten 'LinuxGamepadReader' (ui_dashboard.py),
     der Linux-Input-Events direkt via /dev/input/event* über die Standardbibliothek
     (struct & select) verarbeitet. Es wird KEIN externes 'evdev' C-Modul benötigt!
3. YouTube & Netzwerk:
   - Der Extractor nutzt das systemeigene curl bzw. urllib.request mit nativer
     System-TLS-Unterstützung. Es wird KEIN 'requests'-Paket benötigt.
4. FFT-Audio-Visualizer:
   - Arbeitet bei Verfügbarkeit von 'numpy' mit echter 32-Band FFT-Analyse.
   - Falls 'numpy' nicht vorhanden ist, greift automatisch der integrierte
     Zero-Dependency-Fallback (struct) ohne Fehlermeldung oder Absturz.
   - Für maximale FFT-Präzision können kompilierte aarch64 Python 3.11 Wheels
     (z. B. numpy für manylinux2014_aarch64) in diesen Ordner entpackt werden.
