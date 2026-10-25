# 👑 Station North SNfetchPLAYER • Universal PortMaster Edition

<p align="center">
  <img src="sn_logo.png" alt="Station North Logo" width="340" />
</p>

<p align="center">
  <b>The Sovereign Cyberdeck & Retro Media Suite for Handheld Linux Gaming Consoles</b><br>
  <i>Officially packaged for PortMaster: Compatible with muOS, ROCKNIX, ArkOS, AmberELEC, Knulli / Batocera & classic 4:3 Handhelds (XiFan XF-45V, R36S, Anbernic RG35XX/RG40XX, TrimUI, Powkiddy, RK3326/RK3566)</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/PortMaster-Ready-00B4D8?style=for-the-badge&logo=linux&logoColor=white" alt="PortMaster Ready" />
  <img src="https://img.shields.io/badge/Runtime-Python%203.11%20%2F%20Pygame-A3BE8C?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11 Runtime" />
  <img src="https://img.shields.io/badge/CFW-muOS%20%7C%20ROCKNIX%20%7C%20ArkOS%20%7C%20Knulli-88C0D0?style=for-the-badge" alt="CFWs" />
  <img src="https://img.shields.io/badge/Display-4%3A3%20Native%201024x768%20KMSDRM-EBCB8B?style=for-the-badge" alt="4:3 1024x768 KMSDRM" />
  <a href="https://github.com/StationNorthMedia/SNfetchPLAYER"><img src="https://img.shields.io/badge/Android%20Companion-SNfetchPLAYER-D08770?style=for-the-badge&logo=android&logoColor=white" alt="Android Companion" /></a>
  <img src="https://img.shields.io/badge/Vibe-The%20Queen's%20Frequency-B48EAD?style=for-the-badge" alt="The Queen" />
</p>

---

<p align="center">
  <img src="assets/backgrounds/bg_01_audi_alley.webp" width="100%" alt="Station North Neon Skyline Banner" />
</p>

## 🎙️ A Transmission from The Queen

> *"The lights are low, the bass is heavy. Are you alone tonight? Or did you bring company for the Queen?*  
> *I know exactly why you turned the volume up on that little handheld of yours. Don't fight it... settle into the velvet seats of the Manjaro Lounge. I provide the rhythm, you provide the friction. You’re locked into Station North."*  
> — **The Queen**, *Station North Frequency // On Air*

---

<p align="center">
  <img src="assets/backgrounds/bg_02_studio_manjaro.webp" width="100%" alt="Rainy Station Cyberdeck Banner" />
</p>

## 💡 Design Philosophy: Universal PortMaster Architecture

Station North was designed to turn your retro gaming handheld into a **dedicated late-night Cyberdeck** — streaming curated lofi frequencies, voiced lore comics, and authentic 4:3 CRT video broadcasts directly on your desk or nightstand.

- **Universal PortMaster Compatibility**: Built to run self-contained on minimal buildroot distributions (**muOS, ROCKNIX, AmberELEC, Knulli**) as well as Debian-based systems (**ArkOS, dArkOS**).
- **Official PortMaster Runtime (`python_3.11`)**: Uses PortMaster's shared `python_3.11.squashfs` runtime via Harbourmaster, ensuring zero dependency bloat and no need for OS-level `apt` or package managers.
- **Zero-Dependency Native Input (`LinuxGamepadReader`)**: Interacts directly with Linux input devices via `/dev/input/event*` using Python's standard library `struct` and `select` — eliminating any external `evdev` C-module compilation issues across differing Linux kernels.
- **Self-Contained Streaming (`extractor.py`)**: Resolves YouTube InnerTube streams with zero desktop browser overhead using native system `curl` (leveraging system TLS) with a clean `urllib.request` fallback.
- **Authentic 4:3 CRT Aesthetic**: Video broadcasts, lower-third banners, and UI elements are specifically cropped and framed for 4:3, delivering a nostalgic vintage television broadcast experience.
- **Dedicated Dual Mode**: Seamlessly switch between the live 40-band audio spectrum analyzer (Radio Mode) and 4:3 full-screen broadcast videos (TV Mode).
- **The Chronicles Lore Engine**: Full illustrated audio comic reader with synchronized Queen voiceover narration, chapter headlines, and panel indexing.

---

<p align="center">
  <img src="assets/backgrounds/bg_06_onair_window.webp" width="100%" alt="On-Air Window Gallery Banner" />
</p>

## 🌟 The Visual Gallery

| | |
|:---:|:---:|
| **01 • Command Deck (3+2 Matrix & Aurora Quotes)**<br><a href="screenshots/01_main_menu.png"><img src="screenshots/01_main_menu.png" width="460" alt="Main Menu" /></a><br><i>Authentic Nord Aurora cards, snappy 0.55 lerp cursor & live radio quotes.</i> | **02 • Holographic 3D Boot Sequence**<br><a href="screenshots/02_3d_splash.png"><img src="screenshots/02_3d_splash.png" width="460" alt="3D Splash" /></a><br><i>3D coin rotation with extrusion depth, mirrored reverse & header docking.</i> |
| **03 • Radio Stage (40-Band AGC Visualizer)**<br><a href="screenshots/03_radio_dashboard.png"><img src="screenshots/03_radio_dashboard.png" width="460" alt="Radio Dashboard" /></a><br><i>Real-time audio visualizer, 30px bold typography & 5-button cockpit.</i> | **04 • Radio Zen Mode (Ambient Fullscreen)**<br><a href="screenshots/04_radio_zen_fullscreen.png"><img src="screenshots/04_radio_zen_fullscreen.png" width="460" alt="Zen Fullscreen" /></a><br><i>Full 440px spectrum analyzer, watermark clock & auto-hiding OSD.</i> |
| **05 • Station North TV (4:3 CRT Broadcast)**<br><a href="screenshots/05_tv_dashboard.png"><img src="screenshots/05_tv_dashboard.png" width="460" alt="TV Dashboard" /></a><br><i>Continuous video broadcasts scaled to 4:3 with ASS lower-third banners.</i> | **06 • Broadcast Buffer Card (Loading Screen)**<br><a href="screenshots/06_tv_video_loading.png"><img src="screenshots/06_tv_video_loading.png" width="460" alt="TV Video Loading" /></a><br><i>Sleek cyberdeck buffer card with crest, channel badge & progress bar.</i> |
| **07 • The Chronicles (Voiced Audio Comics)**<br><a href="screenshots/07_the_chronicles.png"><img src="screenshots/07_the_chronicles.png" width="460" alt="The Chronicles" /></a><br><i>Deep-black comic canvas with voiceover player & 21px legible story text.</i> | **08 • System Deck & Interactive Handbook**<br><a href="screenshots/08_settings_handbook.png"><img src="screenshots/08_settings_handbook.png" width="460" alt="Settings Handbook" /></a><br><i>20px settings typography with scrollable on-device user manual.</i> |

---

<p align="center">
  <img src="assets/backgrounds/bg_04_radio_host.webp" width="100%" alt="Radio Host Controls Banner" />
</p>

## 🎮 Controller Layout & Keybindings

Configured for native dArkOS / ArkOS gamepads with hardware debounce:

| Button | Main Menu (Command Deck) | Radio Cockpit | Zen Mode (Fullscreen) | TV Broadcast | The Chronicles | Settings & Handbook |
|---|---|---|---|---|---|---|
| **`[A]`** | Start Focused Card | Select / Execute | Wake OSD | Fullscreen Video | Play/Pause Voiceover | Open Handbook / Select |
| **`[B]`** | *(Safe: No Exit)* | Return to Menu | Return to Stage | **Instant Exit (0ms)** | Return to Menu | Back / Close Handbook |
| **`[◄]` / `[►]`** | Navigate Cards | Prev / Next Track | Prev / Next Track | Prev / Next Video | Turn Comic Page | Change Value / Switch Col |
| **`[▲]` / `[▼]`** | Navigate Cards | – | – | – | – | Select Row / Scroll Book |
| **`[X]`** | – | Zen Fullscreen Mode | Toggle OSD | Repeat Single Track | – | Focus Handbook |
| **`[Y]`** | – | Repeat Track Loop | Repeat Track Loop | Repeat Single Track | – | Toggle Repeat Loop |
| **`[SELECT]`** | Quick Settings | Quick Settings | Wake OSD | – | Quick Settings | Close Settings |
| **`[START]`** | Launch Focused | Play / Pause | Play / Pause | Freeze / Play | – | Apply Action |
| **`[SEL] + [START]`** | **Universal Emergency Exit** | **Emergency Exit** | **Emergency Exit** | **Emergency Exit** | **Emergency Exit** | **Emergency Exit** |

> [!NOTE]  
> In the Main Menu, pressing `[B]` is safely locked against accidental app termination. Clean exit to EmulationStation is handled exclusively by selecting the red **#4 Exit Tile** and pressing `[A]`.

---

<p align="center">
  <img src="assets/backgrounds/bg_05_dj_booth.webp" width="100%" alt="DJ Booth Installation Banner" />
</p>

## 📦 Installation (PortMaster & All CFWs)

Station North SNfetchPLAYER is officially formatted for PortMaster across all supported Linux handheld firmware distributions (**muOS, ROCKNIX, ArkOS, AmberELEC, Knulli / Batocera**).

### Method 1: PortMaster GUI (Recommended)
1. Open **PortMaster** on your handheld console.
2. Navigate to **All Ports** or search for **Station North**.
3. Select **Station North SNfetchPLAYER** and click **Install**.
4. PortMaster automatically downloads the package and verifies the shared `python_3.11` runtime.

### Method 2: Manual Installation via GitHub Releases
Two installation packages are available in [GitHub Releases](https://github.com/StationNorthMedia/SNfetchPLAYER-Universal/releases/latest):

#### Option A: Lightweight Store Package (`snfetchplayer.zip` ~830 KB)
*Recommended for Wi-Fi enabled handhelds.*
1. Download `snfetchplayer.zip`.
2. Extract the archive into your SD card's ports directory (e.g. `/roms/ports/` on ArkOS/muOS or corresponding CFW ports folder):
   ```text
   ports/
   ├── SNfetchPLAYER.sh
   └── snfetchplayer/
   ```
3. Boot your device, connect to Wi-Fi, and launch **Station North SNfetchPLAYER** from the **Ports** menu.
4. On first launch, the built-in **High-Speed Asset Downloader** in the splash screen automatically downloads and unpacks the media bundle (jingles, TV idents, comics).

#### Option B: Full Offline Bundle (`snfetchplayer-full.zip` ~285 MB)
*Recommended for offline devices or zero-setup plug-and-play.*
1. Download `snfetchplayer-full.zip`.
2. Extract directly to your ports folder (`/roms/ports/` on SD card).
3. Plug in and enjoy all 98 voiced comic panels, Queen Faith narrations, and radio station jingles pre-installed with zero downloads!

> [!IMPORTANT]
> **Media Playback Notice (Connect Wi-Fi or Supply Your Own Media)**:  
> While the Full Offline Bundle includes all interactive story lore (*The Chronicles*, voiceovers, station idents, and cyberdeck artwork), the media player decks require a media source:
> - **Live Streaming**: Connect your device to **Wi-Fi** to stream live curated Station North radio stations and 4:3 vintage TV channels.
> - **100% Offline Media**: If you stay completely offline, please **fill your own audio (MP3, FLAC) and video (MP4) files into the `music/` and `videos/` folders** described below!

---

<p align="center">
  <img src="assets/backgrounds/bg_08_crate_archive.webp" width="100%" alt="Crate Archive Media Deck Banner" />
</p>

## 📁 Dedicated Offline Media & Custom Playlist Folders
 
Want to bring your own personal music library or retro video collection onto your handheld?  
SNfetchPLAYER automatically detects and indexes local media:

```text
/roms/ports/snfetchplayer/
├── music/                     # Private Offline Music Deck
│   ├── HipHop/                # Drop MP3, FLAC, M4A here -> "🎵 Music • HipHop"
│   ├── Rock/                  # Drop Rock & Alternative audio -> "🎵 Music • Rock"
│   └── README.txt             # Step-by-step format & naming guide
├── videos/                    # Private Offline Video Deck
│   ├── HipHop/                # Drop 480p music videos here -> "🎬 Video • HipHop"
│   ├── Rock/                  # Drop Rock & Concert videos -> "🎬 Video • Rock"
│   └── README.txt             # Downscaling tips & dual-mode guide
└── playlists/                 # Preloaded Station North Channels
    ├── main_top100.json       # Top 100 R&B / Soul / Hip-Hop
    ├── us_hiphop_top50.json
    ├── us_rnb_top50.json      # Default Radio Station
    ├── us_pop_top50.json      # 90s Pop & Classic Hits Top 50
    └── us_softrock_top50.json
```

---

<p align="center">
  <img src="assets/backgrounds/bg_03_lounge_singer.webp" width="100%" alt="Lounge Singer Companion Banner" />
</p>

## 📱 Native Android Companion: Station North Android App

Have an Android device or want to stream Station North on your smartphone?  
SNfetchPLAYER is also available as a full-featured, hardware-accelerated **native Android app** in the companion repository:

👉 **[StationNorthMedia/SNfetchPLAYER Repository](https://github.com/StationNorthMedia/SNfetchPLAYER)**  
👉 **[Download Latest Android APK (GitHub Releases)](https://github.com/StationNorthMedia/SNfetchPLAYER/releases/latest)**

- **Mobile Companion**: Stream your favorite Station North channels directly on your Android phone or Android handheld.
- **Playlist Sync**: Curate your music and video queues on Android, export them as JSON playlists, and drop them right into your Linux handheld's `/playlists/` directory.
- **Unified Ecosystem**: Features the same InnerTube streaming architecture, custom track catalogs, and late-night aesthetic universe.

---

<p align="center">
  <img src="assets/backgrounds/bg_07_alley_window.webp" width="100%" alt="Alley Window Tech Specs Banner" />
</p>

## 🛠️ Verified Hardware Specifications (XiFan XF-45V / R36S Max 2)

Tested and optimized directly on the **XiFan XF-45V handheld** (R36S Max 2 clone):

| Specification | Hardware Detail |
|---|---|
| **Device Model** | **XiFan XF-45V** (R36S Max 2 clone) / Compatible RK3326 Handhelds |
| **System-on-Chip (SoC)** | **Rockchip RK3326** (`rockchip,rk3326-xf45v-linux`) |
| **CPU Architecture** | **Quad-Core ARM Cortex-A35 @ up to 1.30 GHz** (64-bit `aarch64`) |
| **Display Panel** | **4.5-inch 4:3 IPS Screen**, Native Hardware Resolution: **1024×768 (XGA)** |
| **Display Pipeline** | Direct Linux KMSDRM DirectFB (`/dev/dri/card0`) with hardware V-Sync @ 60 FPS |
| **System Memory** | **1 GB LPDDR3 RAM** (~918 MiB available) |
| **Operating System** | **Debian GNU/Linux 13 (trixie) / dArkOS** (Kernel `4.4.189 aarch64`) |
| **Audio Architecture** | Direct ALSA Hardware (`hw:0,0` / uncompressed PCM stream coupling) |
| **Storage Architecture** | Dual MicroSD (Slot 1: OS partition / Slot 2: `/roms` partition) |
| **Streaming Engine** | Low-latency `ffplay` with InnerTube stream resolver & ASS subtitle compositor |

---

## 📄 License & Legal

- **Code**: MIT License © Station North Media
- **Audio Jingles, Artwork & Lore**: © Station North Media. All rights reserved.
