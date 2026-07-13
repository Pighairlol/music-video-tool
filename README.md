# Music Video Tool

A Windows desktop utility that turns every supported audio file in a selected folder into an MP4 using one cover image.

## Installer

GitHub Actions builds `MusicVideoTool_Setup.exe`. The installer contains the application, its Python runtime, interface libraries, and FFmpeg. End users do not need to install Python or FFmpeg separately.

## Features

- Batch conversion for FLAC, MP3, WAV, M4A, AAC, OGG, OPUS, and WMA
- Cover-image preview
- 1080p, 1440p, 4K, square, and original-size output
- Fit, crop, and stretch modes
- Optional subfolder scanning
- Skip or overwrite existing outputs
- Progress, cancellation, activity log, and accurate failure reporting
- Bundled FFmpeg with only a compact readiness indicator in the interface
- Settings stored in the user's AppData folder

## Building locally on Windows

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --onedir --noupx --name "Music Video Tool" --collect-all customtkinter --hidden-import PIL._tkinter_finder app.py
```

Place `ffmpeg.exe` inside `dist\Music Video Tool\`, install Inno Setup 6, then compile `installer.iss`.
