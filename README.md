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

- Windows 10 or 11
- Python 3.10 or 3.11 (MediaPipe does not support 3.12+ yet)
- A webcam
- Git (optional, for cloning)

## Windows preparation

1. **Install Python 3.11** from https://www.python.org/downloads/release/python-3119/ (or any 3.10 or 3.11 release).
   During installation, check **"Add python.exe to PATH"**.
2. **Verify the install.** Open Command Prompt or PowerShell and run:
   ```bat
   py -3.11 --version
   ```
   You should see `Python 3.11.x`.
3. **Install Git** (optional) from https://git-scm.com/download/win if you want to clone the repository.
4. **Allow camera access.** Go to **Settings → Privacy & security → Camera** and turn on camera access for desktop apps.

## Installation

Run these commands in Command Prompt or PowerShell:

```bat
git clone https://github.com/AhmedSabry345/zombie-survival.git
cd zombie-survival
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If you don't have Git, download the project as a ZIP from GitHub, extract it, open a terminal in that folder, and start from the `py -3.11 -m venv .venv` line.

## Running the game later

After the first install, you only need:

```bat
cd zombie-survival
.venv\Scripts\activate
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

The game looks for `cartoon_zombie_game_single_bullet.mp3` in the project folder and plays it when you fire. If the file is missing, the game runs silently.

## Troubleshooting

- **`py -3.11` not found:** Reinstall Python and make sure "Add python.exe to PATH" is checked, or use the full path to the Python executable.
- **Camera doesn't open:** Close other apps using the webcam (Zoom, Teams, browser tabs). The game uses camera index `0`; if you have several cameras, change `cv.VideoCapture(0)` in `main.py`.
- **Hands not detected:** Use good lighting and keep your hands in front of the camera.
- **`pip install` fails on MediaPipe:** Confirm the venv was created with Python 3.10 or 3.11 (`python --version` inside the activated venv).
- **Activation blocked in PowerShell:** Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try activating again.

## License

Add your license here (for example, MIT).
