# Zombie Survival (Hand-Tracking Edition)

A webcam-controlled zombie survival game. Your **left hand** fires and reloads, your **right hand** aims and picks your weapon. No keyboard or mouse needed to play.

Built with OpenCV, MediaPipe hand tracking, and pygame.

## Features

- Hand-tracking controls using MediaPipe
- Two weapons: pistol (8-round magazine, high damage) and AK (30-round magazine, autofire)
- Wave-based survival with increasing difficulty
- Zombies with hit locations, limb detachment, and ash/blood effects
- Ammo drops and reloading
- Persistent top-5 leaderboard saved to `leaderboard.json`

## Controls

### Left hand: fire and reload
| Gesture | Action |
|---|---|
| Pinch thumb + index | Fire (hold for AK autofire) |
| Thumb up, other fingers curled | Reload selected weapon |

### Right hand: aim and weapon select
| Gesture | Action |
|---|---|
| Index finger extended | Aim cursor |
| OK sign (thumb + index touching, middle up) | Switch to pistol |
| Index + middle up (ring and pinky curled) | Switch to AK |

### Keyboard
| Key | Action |
|---|---|
| `R` | Reload |
| `Q` | Quit |

Menus are navigated by placing your right index fingertip on a button and pinching with the left hand.

## Requirements

- Python 3.10 or 3.11 (MediaPipe does not support 3.12+ on all platforms yet)
- A webcam
- Windows, macOS, or Linux

## Installation

### Option 1: One command

**macOS / Linux:**
```bash
git clone https://github.com/YOUR_USERNAME/zombie-survival.git
cd zombie-survival
bash setup.sh
```

**Windows (Command Prompt or PowerShell):**
```bat
git clone https://github.com/YOUR_USERNAME/zombie-survival.git
cd zombie-survival
setup.bat
```

The setup script creates a virtual environment, installs the dependencies, and launches the game.

### Option 2: Manual install

```bash
git clone https://github.com/YOUR_USERNAME/zombie-survival.git
cd zombie-survival
python -m venv .venv

# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
python main.py
```

## Project Structure

| File | Purpose |
|---|---|
| `main.py` | Entry point and main game loop |
| `handDetector.py` | MediaPipe hand detection wrapper |
| `controls.py` | Gesture recognition (fire, reload, weapon select, ready) |
| `visuals.py` | Aim cursor drawing |
| `second_window.py` | Menus, leaderboard, controls screen, and the game panel |
| `zombie_scene.py` | Zombies, weapons, bullets, effects, and rendering |
| `leaderboard.json` | Saved high scores (created automatically) |
| `requirements.txt` | Python dependencies |

## Optional: Shot sound

The game looks for `cartoon_zombie_game_single_bullet.mp3` in the project folder and plays it when you fire. If the file is missing, the game runs silently. Add your own MP3 with that name to enable sound.

## Troubleshooting

- **Camera doesn't open:** Make sure no other app is using the webcam. The game opens camera index `0`; if you have multiple cameras, change `cv.VideoCapture(0)` in `main.py`.
- **Hands not detected:** Use good lighting and keep your hands in front of the camera.
- **`pip install` fails on MediaPipe:** Confirm you're on Python 3.10 or 3.11.
- **Fullscreen covers the wrong display:** Start the game on the monitor you want, or switch between windowed and fullscreen by using `q` to quit and relaunch.

## License

Add your license here (for example, MIT).
