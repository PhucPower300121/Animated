### Animated

A lightweight desktop tool for viewing and editing animated GIFs.

Built with Python, Tkinter, and Pillow.

Animated focuses on fast workflow, responsive playback, frame scrubbing, and practical editing features instead of bloated UI frameworks or browser-based rendering.

## Features
- Playback
- Smooth animated GIF playback
- Adjustable playback speed (0.25x → 2.0x)
- Pause / resume support
- Frame-by-frame navigation
- Timeline scrubbing
- Toggle looping
## Viewing
- Zoom in / zoom out
- Pan / drag navigation
- Fit-to-window mode
- Reset view
- Transparency checkerboard preview
## Editing
- Crop GIF frames
- Resize GIF dimensions
- Trim frame ranges
- Undo / Redo system
## File Handling
- Drag & drop GIF loading
- Save / Save As support
- Transparent GIF export
- Image information viewer
## Performance
- Background frame resizing thread
- Resize cache system
- Time-based playback engine
- Optimized rendering pipeline

## Screenshots
<img width="802" height="632" alt="python_WPUlT04uMv" src="https://github.com/user-attachments/assets/d170b02f-f4c7-4172-8b38-38e7c7392fd8" />
<img width="802" height="632" alt="python_r4htLvITzx" src="https://github.com/user-attachments/assets/2d7bd26e-a4a9-4ee7-9cd9-24157672e860" />

## Keyboard Shortcuts
| Shortcut |	Action |
|--|--|
| Space |	Play / Pause |
| Left Arrow | Previous frame |
| Right Arrow |	Next frame |
| Ctrl + O | Open GIF |
| Ctrl + S | Save |
| Ctrl + Shift + S | Save As |
| Ctrl + Z | Undo |
| Ctrl + Y | Redo |

## Installation
# Option 1:
- Navigate to `Release Page` from side bar
- Download file `Animated.exe` and run it.

# Option 2:
- Clone the repository:

```
git clone https://github.com/yourname/Animated.git
cd Animated
```

- Install dependencies:

```pip install pillow tkinterdnd2```

- Run the application:

```python GIFV.py```

- Build Executable(Optional):
Using PyInstaller:

```py -m PyInstaller --noconfirm --onefile --windowed --icon "icon.ico" GIFV.py```

## License

This project is licensed under the GNU GPL v3 License.

## Notes

Animated was built as a focused desktop utility for working with animated images without relying on heavyweight frameworks or web technologies.

The UI intentionally stays simple and functional, prioritizing workflow and responsiveness over visual complexity.

## Tech Stack
- Python
- Tkinter
- Pillow
- TkinterDnD2

## Status

The project is currently stable and usable.

Future updates may happen whenever caffeine and motivation align correctly ☕

Developed by [Phúc Power](https://github.com/PhucPower300121)
