"""
MEGA Account Switcher
Quickly switch between multiple MEGAsync accounts.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import os, shutil, json, subprocess, sys, time, zipfile, tempfile, threading, winreg

# ─── Директория скрипта / exe ─────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PATHS_JSON = os.path.join(SCRIPT_DIR, "mega_switcher_paths.json")

# ─── Глобальные пути ──────────────────────────────────────────────────────────
MEGASYNC_EXE  = ""
CONFIG_DIR    = ""
CONFIG_FILE   = ""
PROFILES_DIR  = ""
PROFILES_JSON = ""

# ─── Цветовая схема ───────────────────────────────────────────────────────────
BG          = "#141414"
BG_HEADER   = "#0d0d0d"
BG_LIST     = "#181818"
BG_ITEM     = "#1e1e1e"
BG_ITEM_HOV = "#272727"
BG_ITEM_SEL = "#2d0a0a"
BG_BTN      = "#252525"
MEGA_RED    = "#d90007"
MEGA_RED_H  = "#ff2222"
TEXT        = "#ffffff"
TEXT_DIM    = "#777777"
TEXT_GRAY   = "#aaaaaa"
ACCENT_W    = 3

# ══════════════════════════════════════════════════════════════════════════════
#  Пути
# ══════════════════════════════════════════════════════════════════════════════

def _auto_find_megasync_exe():
    for env in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(env)
        if base:
            p = os.path.join(base, "MEGAsync", "MEGAsync.exe")
            if os.path.isfile(p):
                return os.path.normpath(p)
    p = os.path.join(SCRIPT_DIR, "MEGAsync.exe")
    return os.path.normpath(p) if os.path.isfile(p) else None

def _auto_find_config_dir():
    for root in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")):
        if not root:
            continue
        p = os.path.join(root, "Mega Limited", "MEGAsync")
        if os.path.isdir(p):
            return os.path.normpath(p)
    la = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.normpath(os.path.join(la, "Mega Limited", "MEGAsync"))

def _load_saved_paths():
    if not os.path.isfile(PATHS_JSON):
        return None, None
    try:
        d = json.load(open(PATHS_JSON, encoding="utf-8"))
        return d.get("megasync_exe"), d.get("config_dir")
    except Exception:
        return None, None

def _save_paths(exe, cfg):
    try:
        json.dump({"megasync_exe": exe, "config_dir": cfg},
                  open(PATHS_JSON, "w", encoding="utf-8"), indent=2)
    except OSError:
        pass

def _apply_globals(exe, cfg):
    global MEGASYNC_EXE, CONFIG_DIR, CONFIG_FILE, PROFILES_DIR, PROFILES_JSON
    MEGASYNC_EXE  = exe
    CONFIG_DIR    = cfg
    CONFIG_FILE   = os.path.join(cfg, "MEGAsync.cfg")
    PROFILES_DIR  = os.path.join(cfg, "profiles")
    PROFILES_JSON = os.path.join(cfg, "profiles", "profiles.json")

def init_paths():
    saved_exe, saved_cfg = _load_saved_paths()
    exe = (os.path.normpath(saved_exe)
           if saved_exe and os.path.isfile(saved_exe)
           else _auto_find_megasync_exe())
    cfg = (os.path.normpath(saved_cfg)
           if saved_cfg and os.path.isdir(saved_cfg)
           else _auto_find_config_dir())

    root = tk.Tk(); root.withdraw()
    try: root.attributes("-topmost", True)
    except tk.TclError: pass

    if not exe or not os.path.isfile(exe):
        messagebox.showinfo("MEGA Switcher", "MEGAsync.exe not found. Please locate it.", parent=root)
        picked = filedialog.askopenfilename(parent=root, title="Select MEGAsync.exe",
                     filetypes=[("EXE", "*.exe"), ("All", "*.*")])
        if picked and os.path.isfile(picked):
            exe = os.path.normpath(picked)
        if not exe or not os.path.isfile(exe):
            messagebox.showerror("MEGA Switcher", "MEGAsync.exe is required.", parent=root)
            root.destroy(); sys.exit(1)

    if not os.path.isdir(cfg):
        os.makedirs(cfg, exist_ok=True)

    _apply_globals(exe, cfg)
    os.makedirs(PROFILES_DIR, exist_ok=True)
    if not os.path.exists(PROFILES_JSON):
        json.dump({}, open(PROFILES_JSON, "w", encoding="utf-8"))
    _save_paths(exe, cfg)
    root.destroy()

# ══════════════════════════════════════════════════════════════════════════════
#  Профили
# ══════════════════════════════════════════════════════════════════════════════

def load_profiles():
    if not os.path.exists(PROFILES_JSON):
        return {}
    try:
        return json.load(open(PROFILES_JSON, encoding="utf-8"))
    except Exception:
        return {}

def save_profiles(profiles):
    json.dump(profiles, open(PROFILES_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

def get_active_profile(profiles):
    for name, info in profiles.items():
        if info.get("active"):
            return name
    return None

# ══════════════════════════════════════════════════════════════════════════════
#  MEGAsync управление
# ══════════════════════════════════════════════════════════════════════════════

def kill_megasync():
    subprocess.run(["taskkill", "/F", "/IM", "MEGAsync.exe"], capture_output=True)
    time.sleep(2.5)

def start_megasync():
    lock = os.path.join(CONFIG_DIR, "megasync.lock")
    try:
        if os.path.exists(lock): os.remove(lock)
    except OSError:
        pass
    subprocess.Popen([MEGASYNC_EXE])

def _is_megasync_running():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq MEGAsync.exe"],
                       capture_output=True, text=True)
    return "MEGAsync.exe" in r.stdout

def _find_active_session_hash():
    import glob
    dbs = [f for f in glob.glob(os.path.join(CONFIG_DIR, "megaclient_statecache15_*.db"))
           if "_status_" not in os.path.basename(f)
           and "_transfers_" not in os.path.basename(f)]
    if not dbs:
        return None
    newest = max(dbs, key=os.path.getmtime)
    base = os.path.basename(newest)
    return base[len("megaclient_statecache15_"):-len(".db")]

def _find_hash_in_profile(profile_dir):
    if not os.path.isdir(profile_dir):
        return None
    for f in os.listdir(profile_dir):
        if (f.startswith("megaclient_statecache15_") and f.endswith(".db")
                and "_status_" not in f and "_transfers_" not in f):
            return f[len("megaclient_statecache15_"):-len(".db")]
    return None

def save_session_to_profile(profile_dir):
    os.makedirs(profile_dir, exist_ok=True)
    copied = 0
    if os.path.exists(CONFIG_FILE):
        shutil.copy2(CONFIG_FILE, os.path.join(profile_dir, "MEGAsync.cfg"))
        copied += 1
    h = _find_active_session_hash()
    if not h:
        return copied, None
    for fname in os.listdir(CONFIG_DIR):
        if h in fname and fname.startswith("megaclient_statecache15_"):
            src = os.path.join(CONFIG_DIR, fname)
            if os.path.isfile(src):
                try: shutil.copy2(src, os.path.join(profile_dir, fname)); copied += 1
                except OSError: pass
    fs_src = os.path.join(CONFIG_DIR, "file-service", h)
    if os.path.isdir(fs_src):
        fs_dst = os.path.join(profile_dir, "file-service", h)
        if os.path.exists(fs_dst): shutil.rmtree(fs_dst)
        try: shutil.copytree(fs_src, fs_dst); copied += 1
        except OSError: pass
    return copied, h

def restore_session_from_profile(profile_dir):
    cfg = os.path.join(profile_dir, "MEGAsync.cfg")
    if os.path.exists(cfg):
        shutil.copy2(cfg, CONFIG_FILE)
    h = _find_hash_in_profile(profile_dir)
    if not h:
        return
    for fname in os.listdir(profile_dir):
        if fname.startswith("megaclient_statecache15_") and h in fname:
            src = os.path.join(profile_dir, fname)
            dst = os.path.join(CONFIG_DIR, fname)
            if os.path.isfile(src) and not os.path.exists(dst):
                try: shutil.copy2(src, dst)
                except OSError: pass
    fs_src = os.path.join(profile_dir, "file-service", h)
    fs_dst = os.path.join(CONFIG_DIR, "file-service", h)
    if os.path.isdir(fs_src) and not os.path.isdir(fs_dst):
        try: shutil.copytree(fs_src, fs_dst)
        except OSError: pass

# ══════════════════════════════════════════════════════════════════════════════
#  Экспорт / Импорт
# ══════════════════════════════════════════════════════════════════════════════

def export_profiles(zip_path):
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(PROFILES_DIR):
            for fname in files:
                fp = os.path.join(root, fname)
                zf.write(fp, os.path.relpath(fp, PROFILES_DIR))
                count += 1
    return count

def import_profiles(zip_path):
    imported, skipped = 0, []
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)
        pj = os.path.join(tmp, "profiles.json")
        if not os.path.exists(pj):
            raise ValueError("profiles.json not found in archive.")
        arc = json.load(open(pj, encoding="utf-8"))
        existing = load_profiles()
        for name, info in arc.items():
            if name in existing:
                skipped.append(name); continue
            src = os.path.join(tmp, name)
            dst = os.path.join(PROFILES_DIR, name)
            if os.path.isdir(src): shutil.copytree(src, dst)
            else: os.makedirs(dst, exist_ok=True)
            existing[name] = {k: v for k, v in info.items() if k != "active"}
            existing[name]["active"] = False
            imported += 1
        save_profiles(existing)
    return imported, skipped

# ══════════════════════════════════════════════════════════════════════════════
#  Автозапуск
# ══════════════════════════════════════════════════════════════════════════════

_AUTOREG  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTONAME = "MEGA-Switcher"

def is_autostart_enabled():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOREG)
        winreg.QueryValueEx(k, _AUTONAME)
        winreg.CloseKey(k)
        return True
    except (FileNotFoundError, OSError):
        return False

def set_autostart(enable):
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOREG, 0, winreg.KEY_SET_VALUE)
    if enable:
        if getattr(sys, "frozen", False):
            cmd = f'"{sys.executable}" --silent'
        else:
            cmd = f'pythonw "{os.path.abspath(__file__)}" --silent'
        winreg.SetValueEx(k, _AUTONAME, 0, winreg.REG_SZ, cmd)
    else:
        try: winreg.DeleteValue(k, _AUTONAME)
        except FileNotFoundError: pass
    winreg.CloseKey(k)

# ══════════════════════════════════════════════════════════════════════════════
#  Тост-уведомление Windows
# ══════════════════════════════════════════════════════════════════════════════

def _toast(title, message):
    try:
        import ctypes
        NIIF_INFO = 0x01
        NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
        NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 1, 2, 4, 0x10
        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize",        ctypes.c_ulong),
                ("hWnd",          ctypes.c_void_p),
                ("uID",           ctypes.c_uint),
                ("uFlags",        ctypes.c_uint),
                ("uCallbackMsg",  ctypes.c_uint),
                ("hIcon",         ctypes.c_void_p),
                ("szTip",         ctypes.c_wchar * 128),
                ("dwState",       ctypes.c_ulong),
                ("dwStateMask",   ctypes.c_ulong),
                ("szInfo",        ctypes.c_wchar * 256),
                ("uTimeout",      ctypes.c_uint),
                ("szInfoTitle",   ctypes.c_wchar * 64),
                ("dwInfoFlags",   ctypes.c_ulong),
            ]
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.uID = 1
        nid.uFlags = NIF_ICON | NIF_TIP | NIF_INFO
        nid.szTip = "MEGA Switcher"
        nid.szInfo = message[:255]
        nid.szInfoTitle = title[:63]
        nid.dwInfoFlags = NIIF_INFO
        shell32 = ctypes.windll.shell32
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        time.sleep(3)
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
#  Кастомный список профилей
# ══════════════════════════════════════════════════════════════════════════════

class ProfileListWidget(tk.Frame):
    """Scrollable MEGA-style profile list with proper hover/select."""

    def __init__(self, parent, on_select, on_double, **kw):
        super().__init__(parent, bg=BG_LIST, **kw)
        self._on_select = on_select
        self._on_double = on_double
        self._selected  = None          # currently selected profile name
        # name → (outer, accent, [all_bg_widgets])
        self._rows: dict[str, tuple] = {}

        self._canvas = tk.Canvas(self, bg=BG_LIST, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview,
                          bg=BG_LIST, troughcolor="#1e1e1e", bd=0, width=5,
                          relief="flat", activerelief="flat")
        self._canvas.configure(yscrollcommand=sb.set)
        self._inner = tk.Frame(self._canvas, bg=BG_LIST)
        self._win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._win_id, width=e.width))
        # Mouse-wheel scroll (bind to canvas only to avoid global conflict)
        self._canvas.bind("<Enter>",
            lambda e: self._canvas.bind_all("<MouseWheel>", self._on_wheel))
        self._canvas.bind("<Leave>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"))

        self._canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _on_wheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Обновление списка ─────────────────────────────────────────────────────
    def refresh(self, profiles: dict, active: str):
        for w in self._inner.winfo_children():
            w.destroy()
        self._rows.clear()
        self._selected = None
        for name in profiles:
            self._add_row(name, name == active)

    def _add_row(self, name: str, is_active: bool):
        # Outer container
        outer = tk.Frame(self._inner, bg=BG_ITEM, pady=0, cursor="hand2")
        outer.pack(fill="x", pady=1, padx=0)

        # Left red accent bar
        accent_clr = MEGA_RED if is_active else BG_ITEM
        accent = tk.Frame(outer, width=ACCENT_W, bg=accent_clr)
        accent.pack(side="left", fill="y")
        accent.pack_propagate(False)

        # Content area
        inner = tk.Frame(outer, bg=BG_ITEM, padx=14, pady=12)
        inner.pack(side="left", fill="both", expand=True)

        # Status dot
        dot_clr = MEGA_RED if is_active else "#3a3a3a"
        dot = tk.Label(inner, text="●", font=("Segoe UI", 8), fg=dot_clr, bg=BG_ITEM)
        dot.pack(side="left", padx=(0, 10))

        # Profile name
        name_font = ("Segoe UI", 11, "bold") if is_active else ("Segoe UI", 11)
        name_clr  = TEXT if is_active else TEXT_GRAY
        lbl = tk.Label(inner, text=name, font=name_font, fg=name_clr,
                       bg=BG_ITEM, anchor="w")
        lbl.pack(side="left", fill="x", expand=True)

        # ACTIVE badge
        badge_widgets = []
        if is_active:
            badge = tk.Label(inner, text=" ACTIVE ", font=("Segoe UI", 7, "bold"),
                             fg=MEGA_RED, bg=BG_ITEM)
            badge.pack(side="right", padx=(0, 4))
            badge_widgets.append(badge)

        # All widgets whose bg we update on hover/select
        bg_widgets = [outer, inner, dot, lbl] + badge_widgets

        self._rows[name] = (outer, accent, bg_widgets)

        # Bind events to every widget in the row
        for w in bg_widgets:
            w.bind("<Button-1>",        lambda e, n=name: self._select(n))
            w.bind("<Double-Button-1>", lambda e, n=name: self._on_double(n))
            w.bind("<Enter>",           lambda e, n=name: self._enter(n))
            w.bind("<Leave>",           lambda e, n=name, ow=outer: self._leave(n, ow, e))

    # ── Цвет строки ───────────────────────────────────────────────────────────
    def _set_row_bg(self, name: str, clr: str):
        if name not in self._rows:
            return
        _, _, bg_widgets = self._rows[name]
        for w in bg_widgets:
            try: w.configure(bg=clr)
            except tk.TclError: pass

    # ── Hover ─────────────────────────────────────────────────────────────────
    def _enter(self, name: str):
        if name != self._selected:
            self._set_row_bg(name, BG_ITEM_HOV)

    def _leave(self, name: str, outer: tk.Frame, event):
        """Only unhover if mouse truly left the row boundaries."""
        try:
            ox = outer.winfo_rootx()
            oy = outer.winfo_rooty()
            ow = outer.winfo_width()
            oh = outer.winfo_height()
            mx, my = event.x_root, event.y_root
            if ox <= mx < ox + ow and oy <= my < oy + oh:
                return   # still inside the row
        except tk.TclError:
            pass
        if name != self._selected:
            self._set_row_bg(name, BG_ITEM)

    # ── Select ────────────────────────────────────────────────────────────────
    def _select(self, name: str):
        prev = self._selected
        self._selected = name
        self._on_select(name)
        if prev and prev in self._rows:
            self._set_row_bg(prev, BG_ITEM)
        self._set_row_bg(name, BG_ITEM_SEL)

    def get_selected(self) -> str | None:
        return self._selected

# ══════════════════════════════════════════════════════════════════════════════
#  Главное окно
# ══════════════════════════════════════════════════════════════════════════════

class MegaSwitcher(tk.Tk):

    def __init__(self, start_hidden: bool = False):
        super().__init__()
        self.title("MEGA Account Switcher")
        self.geometry("400x580")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._set_icon()

        self._selected_name: str | None = None
        self._busy          = False          # True while switching/saving
        self._tray          = None
        self._btn_refs      = []             # кнопки для disable/enable

        self._build_ui()
        self._refresh_list()
        self._start_tray()

        self.protocol("WM_DELETE_WINDOW", self._hide)
        # Сворачивание в трей вместо taskbar
        self.bind("<Unmap>", self._on_minimize)

        if start_hidden:
            self.withdraw()

    # ── Путь к иконке (dev + bundled exe) ────────────────────────────────────
    @staticmethod
    def _ico_path() -> str | None:
        candidates = []
        # 1. Внутри exe (PyInstaller _MEIPASS)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, "app.ico"))
        # 2. Рядом со скриптом / exe
        candidates.append(os.path.join(SCRIPT_DIR, "app.ico"))
        candidates.append(os.path.join(CONFIG_DIR, "app.ico"))
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    # ── Иконка окна ───────────────────────────────────────────────────────────
    def _set_icon(self):
        p = self._ico_path()
        if p:
            try: self.iconbitmap(p); return
            except tk.TclError: pass

    # ── Построение UI ─────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Шапка ─────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG_HEADER)
        hdr.pack(fill="x")

        logo_frame = tk.Frame(hdr, bg=BG_HEADER, pady=16)
        logo_frame.pack(side="left", padx=(18, 0))
        tk.Label(logo_frame, text="M", font=("Segoe UI", 24, "bold"),
                 fg=MEGA_RED, bg=BG_HEADER).pack(side="left")
        tk.Label(logo_frame, text="EGA  Account Switcher",
                 font=("Segoe UI", 14, "bold"),
                 fg=TEXT, bg=BG_HEADER).pack(side="left", padx=(0, 0))

        # ── Подпись секции ────────────────────────────────────────────────────
        sec = tk.Frame(self, bg=BG, padx=18)
        sec.pack(fill="x", pady=(8, 3))
        tk.Label(sec, text="ACCOUNTS", font=("Segoe UI", 8, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(anchor="w")

        # ── Список профилей ───────────────────────────────────────────────────
        lw = tk.Frame(self, bg=BG, padx=18, pady=0)
        lw.pack(fill="both", expand=True)

        self.profile_list = ProfileListWidget(
            lw,
            on_select=lambda n: setattr(self, "_selected_name", n),
            on_double=self._switch_fast,
        )
        self.profile_list.pack(fill="both", expand=True)

        # ── Статус / прогресс ─────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(
            self, textvariable=self.status_var,
            font=("Segoe UI", 8, "italic"), fg=TEXT_DIM, bg=BG,
            anchor="w", padx=20)
        self.status_label.pack(fill="x", pady=(3, 0))

        # ── Разделитель ───────────────────────────────────────────────────────
        tk.Frame(self, bg="#222222", height=1).pack(fill="x", padx=0, pady=(5, 0))

        # ── Панель кнопок ─────────────────────────────────────────────────────
        btns = tk.Frame(self, bg=BG_HEADER, padx=16, pady=14)
        btns.pack(fill="x")
        self._btn_refs.clear()

        def mk_btn(parent, text, cmd, bg=BG_BTN, fg=TEXT_GRAY, **kw):
            b = tk.Button(parent, text=text, command=cmd,
                          bg=bg, fg=fg,
                          activebackground="#333", activeforeground=TEXT,
                          font=("Segoe UI", 9, "bold"), bd=0, relief="flat",
                          cursor="hand2", pady=8, padx=6, **kw)
            self._btn_refs.append(b)
            return b

        # Строка 1: Switch (полная ширина, красная)
        self._btn_switch = mk_btn(btns, "⚡   Switch to selected",
                                  self._switch_selected,
                                  bg=MEGA_RED, fg=TEXT)
        self._btn_switch.pack(fill="x", pady=(0, 8))

        # Строка 2: Save / Rename / Delete
        r2 = tk.Frame(btns, bg=BG_HEADER)
        r2.pack(fill="x", pady=(0, 6))
        mk_btn(r2, "💾  Save current",  self._save_current, fg="#90c8ff"
               ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        mk_btn(r2, "✏  Rename",         self._rename,       fg="#90c8ff"
               ).pack(side="left", fill="x", expand=True, padx=3)
        mk_btn(r2, "🗑  Delete",         self._delete,       fg="#ff8888"
               ).pack(side="left", fill="x", expand=True, padx=(3, 0))

        # Строка 3: Export / Import
        r3 = tk.Frame(btns, bg=BG_HEADER)
        r3.pack(fill="x", pady=(0, 8))
        mk_btn(r3, "📤  Export ZIP", self._export, fg="#80e880"
               ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        mk_btn(r3, "📥  Import ZIP", self._import, fg="#80e880"
               ).pack(side="left", fill="x", expand=True, padx=(3, 0))

        # Строка 4: Автозапуск
        self._auto_var = tk.BooleanVar(value=is_autostart_enabled())
        tk.Checkbutton(btns, text="  Launch with Windows",
                       variable=self._auto_var,
                       font=("Segoe UI", 9), fg=TEXT_DIM,
                       bg=BG_HEADER, activebackground=BG_HEADER,
                       activeforeground=TEXT, selectcolor=BG_BTN,
                       bd=0, cursor="hand2",
                       command=self._toggle_autostart).pack(anchor="w")

    # ── Busy state (кнопки disable/enable) ────────────────────────────────────
    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for b in self._btn_refs:
            try: b.configure(state=state)
            except tk.TclError: pass

    # ── Обновление списка ─────────────────────────────────────────────────────
    def _refresh_list(self):
        profiles = load_profiles()           # всегда свежие данные с диска
        self._profiles = profiles
        active = get_active_profile(profiles)
        self.profile_list.refresh(profiles, active)
        if active:
            self.status_var.set(f"Active: {active}")
        elif profiles:
            self.status_var.set("No active profile — select one")
        else:
            self.status_var.set("No profiles yet — press Save current")
        self._update_tray()

    def _get_sel(self) -> str | None:
        n = self._selected_name
        if not n:
            messagebox.showwarning("No selection",
                "Please select an account from the list.", parent=self)
            return None
        return n

    # ── Switch ────────────────────────────────────────────────────────────────
    def _switch_selected(self):
        name = self._get_sel()
        if name:
            self._do_switch_threaded(name, confirm=True)

    def _switch_fast(self, name: str):
        """Double-click — без подтверждения."""
        self._do_switch_threaded(name, confirm=False)

    def _do_switch_threaded(self, name: str, confirm: bool):
        if self._busy:
            return
        profile_dir = os.path.join(PROFILES_DIR, name)
        if not os.path.exists(os.path.join(profile_dir, "MEGAsync.cfg")):
            messagebox.showerror("Error",
                f"Profile '{name}' has no saved session.\nUse 'Save current' first.",
                parent=self)
            return
        if confirm:
            if not messagebox.askyesno("Switch account",
                    f"Switch to '{name}'?\n\nMEGAsync will restart briefly.",
                    parent=self):
                return

        self._set_busy(True)
        self.status_var.set(f"Switching to {name}…")

        def _work():
            kill_megasync()
            restore_session_from_profile(profile_dir)
            profiles = load_profiles()
            for n in profiles:
                profiles[n]["active"] = (n == name)
            save_profiles(profiles)
            start_megasync()
            self.after(0, self._after_switch)

        threading.Thread(target=_work, daemon=True).start()

    def _after_switch(self):
        self._set_busy(False)
        self._refresh_list()

    def _tray_switch(self, name: str):
        """Переключение из трея — без диалогов."""
        if self._busy:
            return

        def _work():
            profile_dir = os.path.join(PROFILES_DIR, name)
            if not os.path.exists(os.path.join(profile_dir, "MEGAsync.cfg")):
                return
            self.after(0, lambda: self.status_var.set(f"Switching to {name}…"))
            kill_megasync()
            restore_session_from_profile(profile_dir)
            profiles = load_profiles()
            for n in profiles:
                profiles[n]["active"] = (n == name)
            save_profiles(profiles)
            start_megasync()
            self.after(0, self._after_switch)
            threading.Thread(target=_toast,
                args=("MEGA Switcher", f"Switched to: {name}"), daemon=True).start()

        threading.Thread(target=_work, daemon=True).start()

    # ── Save current ──────────────────────────────────────────────────────────
    def _save_current(self):
        if self._busy:
            return
        if not os.path.exists(CONFIG_FILE):
            messagebox.showerror("Error", "MEGAsync.cfg not found.\nIs MEGAsync running?",
                                 parent=self)
            return
        name = simpledialog.askstring("Save account",
                                      "Enter a name for this account:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        profiles = load_profiles()
        if name in profiles:
            if not messagebox.askyesno("Overwrite",
                    f"Overwrite existing profile '{name}'?", parent=self):
                return

        was_running = _is_megasync_running()
        self._set_busy(True)
        self.status_var.set(f"Saving {name}…")

        def _work():
            if was_running:
                kill_megasync()
            profile_dir = os.path.join(PROFILES_DIR, name)
            copied, h = save_session_to_profile(profile_dir)
            p = load_profiles()
            p[name] = {"session_hash": h or "", "active": False}
            save_profiles(p)
            if was_running:
                start_megasync()
            self.after(0, lambda: self._after_save(name, copied))

        threading.Thread(target=_work, daemon=True).start()

    def _after_save(self, name: str, copied: int):
        self._set_busy(False)
        self._refresh_list()
        messagebox.showinfo("Saved", f"Profile '{name}' saved ({copied} file(s)).",
                            parent=self)

    # ── Rename ────────────────────────────────────────────────────────────────
    def _rename(self):
        name = self._get_sel()
        if not name:
            return
        new = simpledialog.askstring("Rename",
                                     f"New name for '{name}':",
                                     initialvalue=name, parent=self)
        if not new or not new.strip() or new.strip() == name:
            return
        new = new.strip()
        profiles = load_profiles()
        if new in profiles:
            messagebox.showerror("Error", f"'{new}' already exists.", parent=self)
            return
        old_dir = os.path.join(PROFILES_DIR, name)
        new_dir = os.path.join(PROFILES_DIR, new)
        if os.path.exists(old_dir):
            os.rename(old_dir, new_dir)
        profiles[new] = profiles.pop(name)
        save_profiles(profiles)
        self._selected_name = new
        self._refresh_list()

    # ── Delete ────────────────────────────────────────────────────────────────
    def _delete(self):
        name = self._get_sel()
        if not name:
            return
        if not messagebox.askyesno("Delete",
                f"Delete profile '{name}'?\nThis cannot be undone.", parent=self):
            return
        d = os.path.join(PROFILES_DIR, name)
        if os.path.exists(d):
            shutil.rmtree(d)
        profiles = load_profiles()
        profiles.pop(name, None)
        save_profiles(profiles)
        self._selected_name = None
        self._refresh_list()

    # ── Export ────────────────────────────────────────────────────────────────
    def _export(self):
        profiles = load_profiles()
        if not profiles:
            messagebox.showwarning("Export", "No profiles to export.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Save backup",
            defaultextension=".zip", initialfile="mega_profiles_backup.zip",
            filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")])
        if not path:
            return
        try:
            count = export_profiles(path)
            size  = os.path.getsize(path) / 1024 / 1024
            messagebox.showinfo("Export done",
                f"Exported {count} file(s)\n{os.path.basename(path)}  ({size:.1f} MB)",
                parent=self)
        except Exception as e:
            messagebox.showerror("Export error", str(e), parent=self)

    # ── Import ────────────────────────────────────────────────────────────────
    def _import(self):
        path = filedialog.askopenfilename(
            parent=self, title="Open backup ZIP",
            filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")])
        if not path:
            return
        try:
            imported, skipped = import_profiles(path)
        except Exception as e:
            messagebox.showerror("Import error", str(e), parent=self)
            return
        self._refresh_list()
        msg = f"Imported {imported} profile(s)."
        if skipped:
            msg += f"\nSkipped (already exist): {', '.join(skipped)}"
        messagebox.showinfo("Import done", msg, parent=self)

    # ── Автозапуск ────────────────────────────────────────────────────────────
    def _toggle_autostart(self):
        try:
            set_autostart(self._auto_var.get())
        except Exception as e:
            messagebox.showerror("Autostart error", str(e), parent=self)
            self._auto_var.set(is_autostart_enabled())

    # ── Трей ─────────────────────────────────────────────────────────────────
    def _tray_icon_image(self):
        """Рисует MEGA-стиль иконку: красный круг + белая M."""
        from PIL import Image, ImageDraw, ImageFont
        size = 128
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, size - 3, size - 3], fill=(215, 0, 7, 255))
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 88)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), "M", font=font)
        x = (size - (bbox[2] - bbox[0])) // 2 - bbox[0]
        y = (size - (bbox[3] - bbox[1])) // 2 - bbox[1] - 4
        draw.text((x, y), "M", fill=(255, 255, 255, 255), font=font)
        return img.resize((64, 64), Image.LANCZOS)

    def _build_tray_menu(self):
        """Строит статическое меню — правильный API pystray."""
        import pystray
        profiles = load_profiles()
        active   = get_active_profile(profiles)
        items    = []

        # Фабрика замыканий — pystray принимает строго 0/1/2 параметра в callback
        def make_cb(n):
            return lambda icon, item: self._tray_switch(n)

        for name in profiles:
            label = ("✓  " if name == active else "      ") + name
            items.append(pystray.MenuItem(label, make_cb(name)))

        if items:
            items.append(pystray.Menu.SEPARATOR)

        items += [
            pystray.MenuItem(
                "Open window",
                lambda i, it: self.after(0, self._show),
                default=True),
            pystray.MenuItem(
                "Launch with Windows",
                lambda i, it: self.after(0, self._toggle_autostart_tray),
                checked=lambda item: is_autostart_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda i, it: self.after(0, self._quit)),
        ]
        return pystray.Menu(*items)   # ← *items, не callable

    def _start_tray(self):
        import pystray
        img = self._tray_icon_image()
        self._tray = pystray.Icon(
            "MEGA-Switcher", img, "MEGA Account Switcher",
            menu=self._build_tray_menu())
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _update_tray(self):
        if self._tray:
            try:
                self._tray.menu = self._build_tray_menu()
                self._tray.update_menu()
            except Exception:
                pass

    def _toggle_autostart_tray(self):
        new = not is_autostart_enabled()
        try:
            set_autostart(new)
            self._auto_var.set(new)
        except Exception:
            pass

    def _on_minimize(self, event):
        """Перехватываем сворачивание → уходим в трей."""
        if event.widget is self:
            self.after(10, self.withdraw)

    # ── Управление окном ─────────────────────────────────────────────────────
    def _show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _hide(self):
        self.withdraw()

    def _quit(self):
        if self._tray:
            self._tray.stop()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    hidden = "--silent" in sys.argv
    init_paths()
    app = MegaSwitcher(start_hidden=hidden)
    app.mainloop()
