# 🐛 Station North SNfetchPLAYER – Bug Tracker & Detail-Analyse

## Gemeldete Beobachtungen des Nutzers:
> 1. „Das Problem ist, dass kurz vor Ende des Videos das Video einfach aufhört, oder das Radio. Das habe ich auch in den Station North IDs [Jingles / TV Idents] drinne.“
> 2. „Und manchmal setzt auch der Equalizer erst später ein, als das Lied schon läuft, nur ein paar Sekunden oder so, als ob da ein Versatz drinne ist.“

---

## 🔍 Tiefenanalyse der beiden Phänomene:

### Phänomen 1: Warum wird am Ende der Songs, Videos und Jingles 1–2 Sekunden abgeschnitten?

**Die Ursache (Audio-Puffer-Drain):**
1. **Bei Radio & Jingles (ffmpeg):**
   * `ffmpeg` dekodiert die MP3/WAV-Datei und schickt das Audio an das Ausgabegerät (ALSA / PulseAudio).
   * Die Linux-Audio-Treiber (ALSA/Pulse) haben einen Ringpuffer (Hardware-Buffer) von ca. **1,0 bis 2,0 Sekunden**.
   * Sobald `ffmpeg` das letzte Audio-Paket in den Treiber geschoben hat, beendet sich der `ffmpeg`-Prozess sofort (`poll() is not None` wird True).
   * Die Python-Hauptschleife merkt: *„Prozess ist beendet!“* und ruft **sofort** `trigger_play_track_async()` auf.
   * `trigger_play_track_async()` ruft als allererstes `stop_audio()` auf – **was den Audio-Puffer von ALSA/Pulse sofort abwürgt und killt**!
   * 👉 **Ergebnis:** Die letzten 1–2 Sekunden des Songs oder Jingles, die noch im Treiber-Puffer lagen, werden mitten im Ausklingen abgeschnitten!

2. **Bei Videos (ffplay):**
   * Bei Videodateien enden Video- und Tonspur in Containern (MP4/MKV) selten auf die Millisekunde genau gleichzeitig.
   * `ffplay` mit `-autoexit` beendet sich standardmäßig sofort, wenn der Video-Decoder das letzte Frame gezeichnet hat – selbst wenn der Ton noch 0,5–1,0s weitergelaufen wäre.
   * Zusätzlich war der Analog-Stick-Schwellwert bei 1200 (Stick-Drift), was bei Bewegung des Geräts vorzeitiges Überspringen auslöste.

**Die Lösung:**
* Nach dem Beenden des Dekoders einen kurzen Drain-Delay / Puffer-Auskling-Timer (ca. 0.8s – 1.2s) abwarten, bevor der Prozess getötet und der nächste Track gestartet wird.

---

### Phänomen 2: Warum setzt der Equalizer (Visualizer) 1–2 Sekunden versetzt/später ein?

**Die Ursache (OS Pipe Buffering):**
1. In `ui_dashboard.py` wird der Audio-Stream aufgeteilt:
   * Zweig 1 geht an die Lautsprecher (`audio_sink_args` -> ALSA/Pulse).
   * Zweig 2 geht als Rohdaten (`s16le`, 22050Hz) an die Standardausgabe (`stdout=subprocess.PIPE`).
2. **Das Linux-Kernel-Pipe-Problem:**
   * Wenn ein Prozess in eine Pipe schreibt, puffert das Betriebssystem standardmäßig **64 Kilobyte (65.536 Bytes)**, bevor es die Daten an Python weiterreicht!
   * Bei 22.050 Hz Mono mit 16-Bit (44.100 Bytes pro Sekunde) dauert es genau:  
     $$\frac{65.536\text{ Bytes}}{44.100\text{ Bytes/s}} \approx \mathbf{1{,}48\text{ Sekunden!}}$$
   * Das Audio kommt also sofort aus den Lautsprechern, aber der Python-Thread bekommt die ersten PCM-Häppchen erst **1,5 Sekunden später**, wenn der 64-KB-Kernel-Puffer voll ist!

**Die Lösung:**
* Zu `ffmpeg` das Flag `-flush_packets 1` hinzufügen!
* Dadurch zwingt man `ffmpeg`, jedes einzelne Audio-Paket sofort ohne Kernel-Verzögerung in die Visualizer-Pipe zu spülen. Der Equalizer tanzt dann ab der ersten Millisekunde synchron zum Ton!
