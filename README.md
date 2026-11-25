# NASA APOD Wallpaper

Sets NASA's [Astronomy Picture of the Day](https://science.nasa.gov/apod/) as your desktop wallpaper every day, and shows a small window with the title, credit and full explanation.

Works on **Windows**, **macOS** and **Linux** (COSMIC, GNOME, KDE Plasma, XFCE, Cinnamon, MATE). No NASA API key needed.

## Download

Get the file for your system from the [latest release](https://github.com/rafabez/nasa-apod-wallpaper/releases/latest):

| System | File |
|---|---|
| Windows 10/11 | `nasa-apod-wallpaper-windows-x64.exe` |
| macOS (Apple Silicon) | `nasa-apod-wallpaper-macos-arm64.zip` |
| Linux x64 | `nasa-apod-wallpaper-linux-x64.tar.gz` |

Put it somewhere permanent first (e.g. `Applications`, `~/.local/bin`, `C:\Users\you\Apps`), then run it once. It:

1. sets today's picture as the wallpaper,
2. shows the info window,
3. schedules itself to run every day at 09:00.

Running it again by hand repeats all three and re-points the schedule if you moved the file.

**First run notes**

- **Windows:** SmartScreen may say "Windows protected your PC" because the exe isn't code-signed. Click *More info* → *Run anyway*.
- **macOS:** the app isn't signed with an Apple Developer ID. Right-click the app → *Open* → *Open*. macOS also asks once to let it control *System Events*; that is what changes the wallpaper.
- **Linux:** `tar -xzf nasa-apod-wallpaper-linux-x64.tar.gz && ./nasa-apod-wallpaper`

## Options

```
nasa-apod-wallpaper                       run now + install the daily schedule
nasa-apod-wallpaper --install --time 07:30  change the daily time
nasa-apod-wallpaper --uninstall           remove the daily schedule
nasa-apod-wallpaper --date 2026-11-22     use the picture of another day
nasa-apod-wallpaper --no-window           only change the wallpaper
```

Settings, log and the last 7 pictures live in:

- Windows: `%LOCALAPPDATA%\nasa-apod-wallpaper\`
- macOS: `~/Library/Application Support/nasa-apod-wallpaper/`
- Linux: `~/.local/share/nasa-apod-wallpaper/`

`config.json` there has `time`, `show_window` and `nasa_api_key`.

## How it works

- **Picture source:** in late 2026 APOD moved to science.nasa.gov, and `api.nasa.gov/planetary/apod` started returning the NASA logo for every date. The app reads science.nasa.gov's public WordPress REST API instead (no key). `api.nasa.gov` is only a fallback, with `DEMO_KEY`, or your own key from [api.nasa.gov](https://api.nasa.gov/) set as `nasa_api_key` or the `NASA_API_KEY` environment variable.
- **Video days:** the video's thumbnail becomes the wallpaper, and the window has a *Watch video* button.
- **Schedule:** no admin rights needed. If the computer was off or asleep at the scheduled time, the run happens at the next chance (login or wake). It runs at most once per new picture.
  - Windows: Task Scheduler task "NASA APOD Wallpaper".
  - macOS: LaunchAgent `~/Library/LaunchAgents/io.github.rafabez.nasa-apod-wallpaper.plist`.
  - Linux: systemd user timer `nasa-apod-wallpaper.timer`.

## Run from source

Python 3.9+:

```bash
git clone https://github.com/rafabez/nasa-apod-wallpaper
cd nasa-apod-wallpaper
pip install -r requirements.txt
python nasa_apod_wallpaper.py
```

The window uses Tkinter. On Linux distros whose Python lacks it (e.g. Pop!_OS), it falls back to GTK3 via PyGObject, or install `python3-tk`.

Tests: `pip install pytest && pytest`

Releases are built by GitHub Actions with PyInstaller on Windows, macOS and Ubuntu runners. Pushing a `v*` tag publishes a release.

## Credits

Pictures and texts belong to their credited authors and NASA's [APOD](https://science.nasa.gov/apod/) team. This project is not affiliated with NASA.

License: MIT.

---

### Português

Coloca a Foto Astronômica do Dia da NASA como papel de parede todo dia, às 09:00, e mostra uma janela com o título, os créditos e a explicação. Baixe o arquivo do seu sistema em [Releases](https://github.com/rafabez/nasa-apod-wallpaper/releases/latest), coloque numa pasta fixa e rode uma vez. Não precisa de chave da NASA. Para mudar o horário: `--install --time 07:30`. Para remover: `--uninstall`.
