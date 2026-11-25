"""Info window with the APOD title, credit and full explanation.

Tkinter everywhere (bundled in the release binaries). When running from source
on a Linux Python without tkinter, falls back to GTK3 (PyGObject).
"""
from __future__ import annotations

import sys
import webbrowser

from .source import APOD_SITE_URL

BG, FG, MUTED, ACCENT, ACCENT_HOVER = "#0b0d17", "#e8eaf2", "#9aa0b4", "#2b3a67", "#3c4f8a"


def _texts(apod: dict) -> tuple[str, str, str, str | None]:
    title = apod.get("title") or "NASA Astronomy Picture of the Day"
    meta = " · ".join(p for p in [apod.get("date") or "",
                                  f"Credit: {apod['copyright']}" if apod.get("copyright") else ""] if p)
    explanation = apod.get("explanation") or "No explanation available."
    video = apod.get("url") if apod.get("media_type") == "video" else None
    return title, meta, explanation, video


def show(apod: dict, footer: str = "", log=None) -> None:
    """Show the window and block until it is closed."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return _show_gtk(apod, footer, log)
    return _show_tk(apod, footer, log)


def _show_tk(apod, footer, log):
    import tkinter as tk
    from tkinter import font as tkfont

    title, meta, explanation, video = _texts(apod)
    try:
        root = tk.Tk()
    except tk.TclError as e:
        if log:
            log.warning("No display, skipping info window: %s", e)
        return
    root.withdraw()  # build hidden, then show: avoids a flash and position glitches
    root.title(f"NASA APOD - {apod.get('date', '')}")
    root.configure(bg=BG)
    root.minsize(380, 260)
    root.bind("<Escape>", lambda _e: root.destroy())

    family = tkfont.nametofont("TkDefaultFont").actual("family")
    tk.Label(root, text=title, fg=FG, bg=BG, font=(family, 15, "bold"), wraplength=520,
             justify=tk.LEFT).pack(padx=16, pady=(14, 2), anchor=tk.W)
    if meta:
        tk.Label(root, text=meta, fg=MUTED, bg=BG, font=(family, 9), wraplength=520,
                 justify=tk.LEFT).pack(padx=16, pady=(0, 8), anchor=tk.W)

    bar = tk.Frame(root, bg=BG)
    bar.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(6, 14))
    if footer:
        tk.Label(bar, text=footer, fg=MUTED, bg=BG, font=(family, 8)).pack(side=tk.LEFT)

    body = tk.Frame(root, bg=BG)
    body.pack(fill=tk.BOTH, expand=True, padx=16)
    text = tk.Text(body, wrap=tk.WORD, height=14, width=64, font=(family, 11), fg=FG, bg=BG,
                   bd=0, highlightthickness=0, spacing2=2, cursor="arrow")
    scroll = tk.Scrollbar(body, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    text.insert("1.0", explanation)
    text.configure(state=tk.DISABLED)

    def button(label, command):
        b = tk.Button(bar, text=label, command=command, bg=ACCENT, fg="white",
                      activebackground=ACCENT_HOVER, activeforeground="white",
                      font=(family, 10, "bold"), bd=0, padx=14, pady=4, cursor="hand2")
        b.pack(side=tk.RIGHT, padx=(8, 0))
        return b

    button("Close", root.destroy).focus_set()
    if video:
        button("Watch video", lambda: webbrowser.open(video))
    button("Open APOD site", lambda: webbrowser.open(APOD_SITE_URL))

    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)  # pop up above other windows, then act normal
    root.after(2000, lambda: root.attributes("-topmost", False))
    root.mainloop()


def _show_gtk(apod, footer, log):
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk
    except Exception as e:  # noqa: BLE001
        if log:
            log.warning("Neither tkinter nor GTK3 available, skipping info window: %s", e)
        return
    if not Gtk.init_check(None)[0]:
        if log:
            log.warning("No display, skipping info window")
        return

    title, meta, explanation, video = _texts(apod)
    css = Gtk.CssProvider()
    css.load_from_data(f"""
        .apod, .apod textview, .apod textview text {{ background-color: {BG}; color: {FG}; }}
        .apod-title {{ font-size: 15pt; font-weight: bold; }}
        .apod-muted {{ color: {MUTED}; font-size: 9pt; }}
        .apod button {{ background: {ACCENT}; color: white; border: none; box-shadow: none;
                       font-weight: bold; padding: 4px 14px; }}
        .apod button:hover {{ background: {ACCENT_HOVER}; }}
    """.encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    win = Gtk.Window(title=f"NASA APOD - {apod.get('date', '')}")
    win.get_style_context().add_class("apod")
    win.set_default_size(580, 440)
    win.set_position(Gtk.WindowPosition.CENTER)
    win.connect("destroy", Gtk.main_quit)
    win.connect("key-press-event",
                lambda w, ev: ev.keyval == Gdk.KEY_Escape and (w.destroy() or True))

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=14)
    win.add(box)

    def label(text, css_class):
        lb = Gtk.Label(label=text, xalign=0, wrap=True, selectable=True)
        lb.get_style_context().add_class(css_class)
        return lb

    box.pack_start(label(title, "apod-title"), False, False, 0)
    if meta:
        box.pack_start(label(meta, "apod-muted"), False, False, 0)

    text = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD,
                        pixels_inside_wrap=2)
    text.get_buffer().set_text(explanation)
    scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
    scroller.add(text)
    box.pack_start(scroller, True, True, 4)

    bar = Gtk.Box(spacing=8)
    box.pack_end(bar, False, False, 0)
    if footer:
        bar.pack_start(label(footer, "apod-muted"), False, False, 0)

    def button(text_, callback):
        b = Gtk.Button(label=text_)
        b.connect("clicked", lambda _b: callback())
        bar.pack_end(b, False, False, 0)
        return b

    close = button("Close", win.destroy)
    if video:
        button("Watch video", lambda: webbrowser.open(video))
    button("Open APOD site", lambda: webbrowser.open(APOD_SITE_URL))

    win.show_all()
    close.grab_focus()
    win.present()
    Gtk.main()


def message(title: str, text: str) -> None:
    """Small dialog for --install/--uninstall results (the release binaries have no console)."""
    print(text)
    if not getattr(sys, "frozen", False):
        return
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, text)
        root.destroy()
    except Exception:  # noqa: BLE001 - printing is enough
        pass
