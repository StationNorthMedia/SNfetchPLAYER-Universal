# 🎨 Station North SNfetchPLAYER – Visual Design Backlog

Ideensammlung und Konzepte für zukünftige Visualizer-Themes & Retro-Effekte (für PortMaster/Pygame und die native Android-App).

---

## Idee 1: Die rotierende Vinyl-Schallplatte (Turntable Mode)
* **Konzept:** 
  * Im unteren Bereich des Bildschirms ragt eine halbe Schallplatte (Vinyl) hervor.
  * Hinter den pulsierenden Spectrum-Bars dreht sich die Platte sanft.
  * Sichtbar sind die Rillen und ein rundes „Station North“-Zentraletikett.
* **Technik:**
  * Der Mittelpunkt liegt knapp unterhalb der unteren Bildschirmkante (nur obere Hälfte sichtbar).
  * Dreheffekt über rotierende Lichtglanz-Kegel (anisotrope Reflexion) oder simple Textur-Rotation um die Z-Achse.
  * Sehr geringe CPU-Last auf Handhelds (RK3326).

---

## Idee 2: Das Retro-Mixtape / Cassette Deck (Tape Mode)
* **Referenz-Asset:** `assets/ui/cassette_tdk_d90.png` (Transparente TDK D90 Kassette, bereits 180° aufrecht gedreht).
* **Konzept & Schichten (Layering):**
  1. **Hintergrund:** CRT Scanlines / Sternenhimmel / abgedunkeltes Dashboard.
  2. **Schallwellen / Visualizer:** Die Audio-Frequenzbalken leuchten von hinten durch die transparente Kassettenhülle durch!
  3. **Rotierende Spulen (Zahnräder):** 
     * Linkes Zahnrad (voller Bandwickel): Dreht sich langsam (`x ≈ 178, y ≈ 177`).
     * Rechtes Zahnrad (leere Spule): Dreht sich synchron (`x ≈ 376, y ≈ 177`).
  4. **Kassetten-Gehäuse (Vorderseite):** 
     * Das transparente TDK D90 Gehäuse mit Alpha-Transparenz (Glas/Acryl-Optik).
     * Eckschrauben, Typenbezeichnung („IEC I / TYPE I“) und Bandführung bleiben plastisch sichtbar.
  5. **Lichtreflex-Effekt (Glass Glare):**
     * Ein subtiler schräger Glanzstreifen / Lichtschein über dem Acrylglas, der bei Beat-Drops oder im Leerlauf leicht wandert.
* **Vorteile:**
  * Absoluter Retro-Traum: Jeder, der in den 80ern/90ern aufgewachsen ist, kennt genau diese transparente TDK-Kassette.
  * Passt perfekt im 3:2 Querformat auf unsere 4:3 Displays (640×480 und 1024×768).
  * Minimale Rechenlast: Nur die zwei kleinen Zahnrad-Sprites werden um die eigene Achse rotiert.

---

## Option für die Zukunft: Theme-Umschaltung
* Im OSD / Settings-Menü wählbar:
  1. **Classic CRT**: Reiner Spectrum Analyzer mit Phosphor-Glow.
  2. **Vinyl Deck**: Rotierende Schallplatte.
  3. **Cassette Tape**: Animiertes Retro-Mixtape mit Zahnrädern.
