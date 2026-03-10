"""
BESM 2nd Edition Character Creator
Multi-character tabs. Each tab is an independent CharacterTab with its own
CharacterState. Pages read from / write to the state of their parent tab.
Creator: Cornebre
Contributor: -
Tool used: claude.ai (Cornebre)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import math, json, re, sys, shutil, ast, tomllib, pathlib

# ─────────────────────────────────────────────────────────────────────────────
#  PATH RESOLUTION  — works both as a plain .py and as a PyInstaller .exe
# ─────────────────────────────────────────────────────────────────────────────

def _exe_dir() -> pathlib.Path:
    """Directory that contains the running executable (or script in dev mode)."""
    if getattr(sys, "frozen", False):
        # PyInstaller .exe — sys.executable is the .exe itself
        return pathlib.Path(sys.executable).parent
    return pathlib.Path(__file__).parent

def _bundle_dir() -> pathlib.Path:
    """Directory where PyInstaller extracted bundled data files (_MEIPASS),
    or the script directory in dev mode."""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys._MEIPASS)
    return pathlib.Path(__file__).parent

# The folder where user-editable TOML config files live.
CONFIG_DIR     = _exe_dir() / "BESM2nd Config"

# Default folders for save/load dialogs (used if they exist).
CHARS_DIR      = _exe_dir() / "BESM2nd Characters"
ARSENAL_DIR    = _exe_dir() / "BESM2nd Arsenal"
MECHA_DIR      = _exe_dir() / "BESM2nd Mecha"

def _default_dir(folder: pathlib.Path) -> str | None:
    """Return folder as a string if it exists, else None (dialog uses last-visited)."""
    return str(folder) if folder.exists() else None

# ─────────────────────────────────────────────────────────────────────────────
#  FIRST-RUN INSTALLER  — shown when CONFIG_DIR is missing or empty
# ─────────────────────────────────────────────────────────────────────────────

def _bundled_tomls() -> list[pathlib.Path]:
    """Return all besm2nd_config_*.toml files bundled with the application."""
    return sorted(_bundle_dir().glob("besm2nd_config_*.toml"))

def _run_install_dialog() -> bool:
    """Show a Tk dialog letting the user choose which bundled TOMLs to install.
    Creates CONFIG_DIR and copies the selected files into it.
    Returns True if at least one file was installed, False if the user cancelled."""
    bundled = _bundled_tomls()
    if not bundled:
        # Nothing to offer — just create the folder and bail out with a message
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        messagebox.showerror(
            "No config files found",
            f"The configuration folder is missing or empty:\n\n  {CONFIG_DIR}\n\n"
            "No bundled TOML files were found to install.\n"
            "Please add at least one  besm2nd_config_XXX.toml  file to that folder."
        )
        return False

    # Read labels from each bundled TOML for nicer display
    def _label(p):
        try:
            with open(p, "rb") as f:
                cfg = tomllib.load(f)
            return cfg.get("lang", {}).get("label", p.stem.split("_")[-1].upper())
        except Exception:
            return p.stem

    root = tk.Tk()
    root.title("BESM 2nd — First-time Setup")
    root.resizable(False, False)
    root.grab_set()

    tk.Label(root, text="Welcome to BESM 2nd Edition Character Creator!",
             font=("Georgia", 11, "bold"), pady=8).pack(padx=20)
    tk.Label(root,
             text=f"The configuration folder does not exist yet:\n{CONFIG_DIR}\n\n"
                  "Select the language file(s) you want to install:",
             justify="left").pack(padx=20)

    # Language checkboxes + default radio on same row
    frame = tk.Frame(root); frame.pack(padx=20, pady=8, fill="x")
    tk.Label(frame, text="Install", font=("Georgia", 9, "bold"), width=8,
             anchor="w").grid(row=0, column=0, sticky="w")
    tk.Label(frame, text="Default", font=("Georgia", 9, "bold"), width=8,
             anchor="w").grid(row=0, column=1, sticky="w", padx=(12, 0))

    labels   = [_label(p) for p in bundled]
    chk_vars = [tk.BooleanVar(value=True) for _ in bundled]
    # Radio var: index of the language to mark as default (0 = first)
    default_var = tk.IntVar(value=0)

    def _on_chk(i):
        # If the currently selected default gets unchecked, move default
        # to the first still-checked language (if any)
        if not chk_vars[i].get() and default_var.get() == i:
            for j, cv in enumerate(chk_vars):
                if j != i and cv.get():
                    default_var.set(j)
                    break

    for i, (p, label, chk_var) in enumerate(zip(bundled, labels, chk_vars)):
        tk.Checkbutton(frame, text=label, variable=chk_var,
                       font=("Georgia", 10),
                       command=lambda i=i: _on_chk(i)
                       ).grid(row=i + 1, column=0, sticky="w")
        rb = tk.Radiobutton(frame, variable=default_var, value=i,
                            font=("Georgia", 10))
        rb.grid(row=i + 1, column=1, padx=(20, 0))

    result = [False]

    def _install():
        selected = [(i, p) for i, (cv, p) in enumerate(zip(chk_vars, bundled)) if cv.get()]
        if not selected:
            messagebox.showwarning("Nothing selected",
                                   "Please select at least one language to install.",
                                   parent=root)
            return
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        default_idx = default_var.get()
        for i, p in selected:
            dest = CONFIG_DIR / p.name
            shutil.copy2(p, dest)
            # Patch default flag in the installed file
            text = dest.read_text(encoding="utf-8")
            is_default = (i == default_idx)
            # Replace existing default line or insert after the label line
            import re as _re
            if _re.search(r"^default\s*=", text, _re.MULTILINE):
                text = _re.sub(r"^(default\s*=\s*)\S+",
                               f"\\g<1>{'true' if is_default else 'false'}",
                               text, flags=_re.MULTILINE)
            else:
                text = _re.sub(r"(label\s*=\s*\"[^\"]*\")",
                               f"\\1\ndefault = {'true' if is_default else 'false'}",
                               text, count=1)
            dest.write_text(text, encoding="utf-8")

        # Create data folders
        for folder in (CHARS_DIR, ARSENAL_DIR, MECHA_DIR):
            folder.mkdir(parents=True, exist_ok=True)

        # Copy bundled native arsenal JSON into ARSENAL_DIR (don't overwrite)
        for src in _bundle_dir().glob("BESM2nd_Native_Arsenal.json"):
            dst = ARSENAL_DIR / src.name
            if not dst.exists():
                shutil.copy2(src, dst)

        result[0] = True
        root.destroy()

    def _cancel():
        root.destroy()

    btn_frame = tk.Frame(root); btn_frame.pack(pady=(0, 12))
    tk.Button(btn_frame, text="Install selected", command=_install,
              width=18).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Cancel / Exit",   command=_cancel,
              width=18).pack(side="left", padx=6)

    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.mainloop()
    return result[0]

# ─────────────────────────────────────────────────────────────────────────────
#  INTERNATIONALISATION
# ─────────────────────────────────────────────────────────────────────────────

# Active language code (e.g. "eng", "fra").  Changed by the language selector.
_LANG = "eng"

# Loaded config dict for the current language.
_cfg  = None

# UI string table  {key: translated_string}
_UI   = {}

# Game-data display names  {english_key: translated_display_name}
_NAMES = {}

def t(key, fallback=None):
    """Look up a UI string by key.  Falls back to the key itself if missing."""
    return _UI.get(key, fallback if fallback is not None else key)

def display_name(eng_key):
    """Return the translated display name for a game-data element.
    Falls back to the English key so saves from other languages stay readable."""
    return _NAMES.get(eng_key, eng_key)

def _available_langs():
    """Discover all besm2nd_config_XXX.toml files in CONFIG_DIR.
    Each entry is (code, label, path, is_default)."""
    langs = []
    for p in sorted(CONFIG_DIR.glob("besm2nd_config_*.toml")):
        code = p.stem.split("_")[-1]   # e.g. "eng" or "fra"
        try:
            with open(p, "rb") as f:
                cfg = tomllib.load(f)
            lang_sec   = cfg.get("lang", {})
            label      = lang_sec.get("label", code.upper())
            is_default = bool(lang_sec.get("default", False))
            langs.append((code, label, p, is_default))
        except Exception:
            pass
    return langs

def _load_config(lang_code):
    """Load besm2nd_config_<lang_code>.toml from CONFIG_DIR."""
    p = CONFIG_DIR / f"besm2nd_config_{lang_code}.toml"
    with open(p, "rb") as f:
        return tomllib.load(f)

def _build_name_table(cfg):
    """Build {english_key: display_name} from every named entry in cfg.
    For English configs key == name, so the table is a no-op passthrough."""
    names = {}
    sections = (
        cfg.get("stat_formulas", {}).get("entries", [])
        + cfg.get("attr_formulas", {}).get("entries", [])
        + cfg.get("attributes",        [])
        + cfg.get("defects",           [])
        + cfg.get("weapon_advantages", [])
        + cfg.get("weapon_defects",    [])
        + cfg.get("mecha_attributes",  [])
        + cfg.get("mecha_defects",     [])
        + list(cfg.get("skills",        {}).values())
        + list(cfg.get("combat_skills", {}).values())
    )
    for entry in sections:
        key  = entry.get("key")  or entry.get("name")
        name = entry.get("name") or key
        if key:
            names[key] = name
    # Campaign setting display names
    for eng_key, display in cfg.get("settings_names", {}).items():
        names[eng_key] = display
    return names

def _apply_lang(lang_code):
    """Load config for lang_code, rebuild all global game-data tables, and
    update the UI string table.  Call this at startup and on language change."""
    global _LANG, _cfg, _UI, _NAMES
    global STAT_FORMULAS, FORMULA_NAMES, _formula_default
    global ATTR_FORMULAS, _attr_formula_fns
    global ATTRIBUTES, ATTR_COSTS, ATTR_MODIFIES
    global DEFECTS, DEFECT_COSTS, DEFECT_MODIFIES
    global WEAPON_ADVANTAGES, WEAPON_DEFECTS, _WA_DICT, _WD_DICT
    global MECHA_ATTRIBUTES, MECHA_DEFECTS, MECHA_BANNED_ATTRS
    global _SEP_ATTR, _SEP_DEF, MECHA_ALL_ATTRIBUTES, MECHA_ALL_DEFECTS
    global SETTINGS, SKILLS, COMBAT_SKILLS

    _LANG = lang_code
    _cfg  = _load_config(lang_code)
    _UI   = _cfg.get("ui", {})
    _NAMES = _build_name_table(_cfg)

    # ── Stat cost formulas ────────────────────────────────────────────────
    STAT_FORMULAS = {}
    for _e in _cfg["stat_formulas"]["entries"]:
        _key = _e.get("key") or _e["name"]
        STAT_FORMULAS[_key] = _compile_stat_formula(_key, _e["expression"])
    FORMULA_NAMES    = list(STAT_FORMULAS.keys())
    _formula_default = STAT_FORMULAS.get("Default")

    # ── Attribute cost formulas ───────────────────────────────────────────
    ATTR_FORMULAS     = []
    _attr_formula_fns = {}
    for _e in _cfg["attr_formulas"]["entries"]:
        _key = _e.get("key") or _e["name"]
        _sanitise_formula(_key, _e["expression"], ("base_cost", "level"))
        _src = f"def _f(base_cost, level): return {_e['expression'].strip()}\n"
        _ns  = {}
        exec(compile(_src, f"<attr_formula:{_key}>", "exec"), _ns)
        _fn  = _ns["_f"]; _fn.__name__ = _key
        _attr_formula_fns[_key] = _fn
        ATTR_FORMULAS.append(_key)

    # ── Attributes & defects (keyed by english key internally) ────────────
    ATTRIBUTES      = [(a.get("key") or a["name"], a["costs"]) for a in _cfg["attributes"]]
    ATTR_COSTS      = dict(ATTRIBUTES)
    ATTR_MODIFIES   = dict(_cfg["attr_modifies"])
    DEFECTS         = [(d.get("key") or d["name"], d["costs"]) for d in _cfg["defects"]]
    DEFECT_COSTS    = dict(DEFECTS)
    DEFECT_MODIFIES = dict(_cfg["defect_modifies"])

    # ── Weapon advantages & defects ───────────────────────────────────────
    WEAPON_ADVANTAGES = [(e.get("key") or e["name"], e["weight"], e["levelled"])
                         for e in _cfg["weapon_advantages"]]
    WEAPON_DEFECTS    = [(e.get("key") or e["name"], e["weight"], e["levelled"])
                         for e in _cfg["weapon_defects"]]
    _WA_DICT = {n: (w, lv) for n, w, lv in WEAPON_ADVANTAGES}
    _WD_DICT = {n: (w, lv) for n, w, lv in WEAPON_DEFECTS}

    # ── Mecha ─────────────────────────────────────────────────────────────
    MECHA_ATTRIBUTES   = [(a.get("key") or a["name"], a["costs"]) for a in _cfg["mecha_attributes"]]
    MECHA_DEFECTS      = [(d.get("key") or d["name"], d["costs"]) for d in _cfg["mecha_defects"]]
    MECHA_BANNED_ATTRS = set(_cfg["mecha"]["banned_attributes"])
    _SEP_ATTR = (t("separator_mecha_only", "── Mecha Only ──"), None)
    _SEP_DEF  = (t("separator_mecha_only", "── Mecha Only ──"), None)
    MECHA_ALL_ATTRIBUTES = [a for a in ATTRIBUTES if a[0] not in MECHA_BANNED_ATTRS] \
                           + [_SEP_ATTR] + MECHA_ATTRIBUTES
    MECHA_ALL_DEFECTS    = DEFECTS + [_SEP_DEF] + MECHA_DEFECTS

    # ── Skills (keyed by english key) ─────────────────────────────────────
    SETTINGS = _cfg["skills_config"]["settings"]
    SKILLS = {
        (v.get("key") or v["name"]): {s: v[s] for s in SETTINGS}
        for v in _cfg["skills"].values()
    }
    COMBAT_SKILLS = {
        (v.get("key") or v["name"]): {**{s: v[s] for s in SETTINGS}, "is_attack": v["is_attack"]}
        for v in _cfg["combat_skills"].values()
    }

# ─────────────────────────────────────────────────────────────────────────────
#  FORMULA SANITISER  — AST whitelist, checked before any exec()
# ─────────────────────────────────────────────────────────────────────────────

# Whitelist of AST node types that are safe in a math-only expression.
_SAFE_NODES = {
    ast.Module, ast.Expression, ast.Expr,
    ast.Constant,
    ast.Name,
    ast.BinOp, ast.UnaryOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
    ast.Mod, ast.Pow,
    ast.USub, ast.UAdd,
    ast.Compare,
    ast.BoolOp,
    ast.IfExp,
    ast.And, ast.Or, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Call,
    ast.Load,
    ast.FunctionDef, ast.Return, ast.If, ast.Pass,
    ast.arguments, ast.arg,
}

_ALLOWED_CALLS = {"min", "max", "abs", "round", "int", "float"}
_ALLOWED_NAMES = {"v", "base_cost", "level", "True", "False", "None"}


def _sanitise_formula(name: str, expr: str, params: tuple) -> None:
    """Parse *expr* as an AST and raise ValueError if it contains any node
    or name that is not on the whitelist.  *params* lists the allowed variable
    names.  On failure the error message names the exact forbidden construct."""
    allowed_names = set(_ALLOWED_NAMES) | set(params) | _ALLOWED_CALLS
    stripped = expr.strip()

    # Build a minimal parseable wrapper
    if any(line.strip().startswith("return") for line in stripped.splitlines()):
        # Multi-line body already has return statements
        body = "\n".join("    " + l for l in stripped.splitlines())
        wrapped = f"def _f({', '.join(params)}):\n{body}\n"
    else:
        wrapped = f"def _f({', '.join(params)}): return {stripped}\n"

    try:
        tree = ast.parse(wrapped, mode="exec")
    except SyntaxError as exc:
        raise ValueError(
            f"Formula '{name}': syntax error — {exc.msg} "
            f"(line {exc.lineno}, col {exc.offset})"
        ) from exc

    for node in ast.walk(tree):
        node_type = type(node)
        if node_type not in _SAFE_NODES:
            raise ValueError(
                f"Formula '{name}': forbidden construct '{node_type.__name__}' "
                f"— only arithmetic expressions are allowed in TOML formulas."
            )
        if node_type is ast.Name and node.id not in allowed_names:
            raise ValueError(
                f"Formula '{name}': unknown name '{node.id}' "
                f"— allowed names are: {sorted(allowed_names)}."
            )
        if node_type is ast.Call:
            func = node.func
            if not (isinstance(func, ast.Name) and func.id in _ALLOWED_CALLS):
                bad = ast.unparse(func) if hasattr(ast, "unparse") else repr(func)
                raise ValueError(
                    f"Formula '{name}': forbidden call '{bad}' "
                    f"— only {sorted(_ALLOWED_CALLS)} are allowed."
                )


# ─────────────────────────────────────────────────────────────────────────────
#  GAME DATA  —  loaded from besm2nd_config_<lang>.toml at startup
# ─────────────────────────────────────────────────────────────────────────────

def _compile_stat_formula(name, expr):
    expr = expr.strip()
    _sanitise_formula(name, expr, ("v",))
    if "\n" in expr or expr.lstrip().startswith("if"):
        body = "\n".join("    " + line for line in expr.splitlines())
        src  = f"def _f(v):\n{body}\n"
    else:
        src = f"def _f(v): return {expr}\n"
    ns = {}
    exec(compile(src, f"<stat_formula:{name}>", "exec"), ns)
    fn = ns["_f"]; fn.__name__ = name
    return fn

# Initialise with the default language at import time.
# Declare globals so they exist before _apply_lang populates them.
STAT_FORMULAS = {}; FORMULA_NAMES = []; _formula_default = None
ATTR_FORMULAS = []; _attr_formula_fns = {}
ATTRIBUTES = []; ATTR_COSTS = {}; ATTR_MODIFIES = {}
DEFECTS = []; DEFECT_COSTS = {}; DEFECT_MODIFIES = {}
WEAPON_ADVANTAGES = []; WEAPON_DEFECTS = []; _WA_DICT = {}; _WD_DICT = {}
MECHA_ATTRIBUTES = []; MECHA_DEFECTS = []; MECHA_BANNED_ATTRS = set()
_SEP_ATTR = ("── Mecha Only ──", None); _SEP_DEF = ("── Mecha Only ──", None)
MECHA_ALL_ATTRIBUTES = []; MECHA_ALL_DEFECTS = []
SETTINGS = []; SKILLS = {}; COMBAT_SKILLS = {}

# ── First-run check: ensure CONFIG_DIR exists and has at least one TOML ───────
_needs_install = (
    not CONFIG_DIR.exists()
    or not any(CONFIG_DIR.glob("besm2nd_config_*.toml"))
)
if _needs_install:
    if not _run_install_dialog():
        # User cancelled or nothing was installed — cannot continue
        sys.exit(0)

_LANGS = _available_langs()

# ── Pick the startup language ─────────────────────────────────────────────────
_defaults = [entry for entry in _LANGS if entry[3]]  # entries with default=true
_LANG_CONFLICT_WARNING = None   # set below if multiple defaults are found

if len(_defaults) > 1:
    # Multiple TOMLs claim default — use the first alphabetically (same order
    # as _available_langs returns them) and queue a warning for after Tk starts.
    _startup_lang = _defaults[0][0]
    _conflicting  = ", ".join(f"{e[1]} ({e[0]})" for e in _defaults)
    _LANG_CONFLICT_WARNING = (
        f"Multiple language files are marked as default:\n\n  {_conflicting}\n\n"
        f"'{_defaults[0][1]}' was used.\n"
        "Please set  default = true  in only one TOML file."
    )
elif len(_defaults) == 1:
    _startup_lang = _defaults[0][0]
else:
    # No default set — fall back to the first available file and warn.
    _startup_lang = _LANGS[0][0] if _LANGS else "eng"
    _available    = ", ".join(f"{e[1]} ({e[0]})" for e in _LANGS)
    _LANG_CONFLICT_WARNING = (
        f"No language file is marked as default.\n\n"
        f"Available languages:  {_available}\n\n"
        f"'{_LANGS[0][1] if _LANGS else 'English'}' was used as fallback.\n"
        "Please set  default = true  in one of your TOML files."
    )

try:
    _apply_lang(_startup_lang)
except ValueError as _formula_err:
    import tkinter as _tk_err_mod
    _err_root = _tk_err_mod.Tk(); _err_root.withdraw()
    _tk_err_mod.messagebox.showerror(
        "Invalid formula in config",
        f"The TOML configuration contains an unsafe formula:\n\n{_formula_err}\n\n"
        "Only arithmetic expressions are allowed.\nThe application cannot start."
    )
    _err_root.destroy()
    raise SystemExit(1) from _formula_err

def attr_cost(base_cost, level, formula="Default"):
    """Cumulative CP cost of an attribute/weapon/defect at `level`."""
    if level <= 0: return 0
    return (_attr_formula_fns.get(formula) or _attr_formula_fns["Default"])(base_cost, level)

def weap_adv_weight(entries):
    """Total advantage weight for a list of (name, level) pairs."""
    total = 0
    for e in entries:
        n = e[0] if isinstance(e, (list, tuple)) else e
        w, _ = _WA_DICT.get(n, (1, False))
        lv   = e[1] if isinstance(e, (list, tuple)) and len(e) > 1 else 1
        total += w * lv
    return total

def weap_def_weight(entries):
    """Total defect weight for a list of (name, level) pairs."""
    total = 0
    for e in entries:
        n = e[0] if isinstance(e, (list, tuple)) else e
        w, _ = _WD_DICT.get(n, (1, False))
        lv   = e[1] if isinstance(e, (list, tuple)) and len(e) > 1 else 1
        total += w * lv
    return total

def _devastating_level(weap):
    """Return the total level of the Devastating advantage on a weapon, or 0.
    Value is capped at 3, since rules limit its own level independent of weapon
    level.  Higher values in data are silently reduced.
    """
    for e in weap.get("advantages", []):
        n = e[0] if isinstance(e, (list, tuple)) else e
        if n == "Devastating":
            lv = e[1] if isinstance(e, (list, tuple)) and len(e) > 1 else 1
            return min(lv, 3)
    return 0

def _ineffective_level(weap):
    """Return the total level of the Ineffective defect on a weapon, or 0.
    Capped at 3 to match Devastating.
    """
    for e in weap.get("defects", []):
        n = e[0] if isinstance(e, (list, tuple)) else e
        if n == "Ineffective":
            lv = e[1] if isinstance(e, (list, tuple)) and len(e) > 1 else 1
            return min(lv, 3)
    return 0

def weapon_cost(weap, level, modifier, attr_formula):
    """CP/MP cost of a weapon. Base cost is 4.
    Gear weapons have 0 base cost; only the modifier applies.
    Devastating adds +1 per level to the final cost.
    Ineffective removes -1 per level from the final cost."""
    is_gear = weap.get("gear") and (
        weap["gear"].get() if hasattr(weap["gear"], "get") else weap["gear"])
    if is_gear:
        return modifier
    return attr_cost(4, level, attr_formula) + modifier + _devastating_level(weap) - _ineffective_level(weap)

def weapon_damage(weap, level):
    """Damage: (5 if Gear else 15) × max(0, level - adv_weight + def_weight)
    + 4 per level of Devastating - 4 per level of Ineffective."""
    mult = 5 if weap.get("gear") and (
        weap["gear"].get() if hasattr(weap["gear"], "get") else weap["gear"]
    ) else 15
    net = level - weap_adv_weight(weap.get("advantages", [])) \
                + weap_def_weight(weap.get("defects", []))
    dmg_bonus = (_devastating_level(weap) - _ineffective_level(weap)) * (1 if (weap.get("gear") and (
        weap["gear"].get() if hasattr(weap["gear"], "get") else weap["gear"])) else 4)
    return max(0, mult * max(0, net) + dmg_bonus)

# (Mecha + Skills globals are populated by _apply_lang above)

# ─────────────────────────────────────────────────────────────────────────────
#  COLOURS
# ─────────────────────────────────────────────────────────────────────────────
BG        = "#1a1a2e"
PANEL     = "#16213e"
CARD      = "#0f3460"
ACCENT    = "#e94560"
ACCENT2   = "#f5a623"
ACCENT3   = "#7b68ee"
TEXT      = "#eaeaea"
TEXT_DIM  = "#8892a4"
ENTRY_BG  = "#0d2137"
BORDER    = "#2a3f5f"
NAV_ACT   = "#e94560"
NAV_INACT = "#2a3f5f"
GREEN     = "#2ecc71"
RED_C     = "#e74c3c"

# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def int_or(var, default=0):
    try:
        return int(var.get())
    except (ValueError, TypeError, AttributeError, tk.TclError):
        return default

def mk_entry(parent, var, width=6, font=("Courier", 10)):
    return tk.Entry(parent, textvariable=var, width=width,
                    bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                    relief="flat", highlightthickness=1,
                    highlightbackground=BORDER, highlightcolor=ACCENT,
                    font=font)

def mk_int_entry(parent, var, width=4, font=("Courier", 8)):
    """Like mk_entry but highlights red when the value isn't a valid integer."""
    e = tk.Entry(parent, textvariable=var, width=width,
                 bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT,
                 font=font)
    def _validate(*_):
        try:
            int(var.get())
            e.config(highlightbackground=BORDER)
        except (ValueError, TypeError):
            try: e.config(highlightbackground=RED_C)
            except Exception: pass
    _tid_holder = []
    def _validate_safe(*a):
        try:
            _validate(*a)
        except Exception:
            # Widget destroyed — remove this trace so it never fires again
            try: var.trace_remove("write", _tid_holder[0])
            except Exception: pass
    _tid = var.trace_add("write", _validate_safe)
    _tid_holder.append(_tid)
    return e

def mk_int_spinbox(parent, var, width=4, font=("Courier", 8), from_=0, to=999):
    """Spinbox for integer entry with validation highlighting and range bounds."""
    sb = tk.Spinbox(parent, textvariable=var, width=width,
                    from_=from_, to=to,
                    bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                    relief="flat", highlightthickness=1,
                    highlightbackground=BORDER, highlightcolor=ACCENT,
                    buttonbackground=CARD, activebackground=CARD,
                    font=font)
    _tid_holder = []
    def _validate(*_):
        try:
            int(var.get())
            sb.config(highlightbackground=BORDER)
        except (ValueError, TypeError):
            try: sb.config(highlightbackground=RED_C)
            except Exception: pass
        except Exception:
            # Widget destroyed — remove this trace so it never fires again
            try: var.trace_remove("write", _tid_holder[0])
            except Exception: pass
    _tid = var.trace_add("write", _validate)
    _tid_holder.append(_tid)
    return sb

def mk_btn(parent, text, cmd, bg=ACCENT, fg="white", small=False):
    f = ("Georgia", 8) if small else ("Georgia", 10, "bold")
    return tk.Button(parent, text=text, command=cmd,
                     bg=bg, fg=fg, relief="flat", cursor="hand2",
                     activebackground=ACCENT2, activeforeground="black",
                     font=f, padx=8, pady=3)

# Registry of all scrollable canvases, innermost-last (registration order).
# A single global wheel handler fires once per event, walks the ancestor
# chain to find all canvases, and scrolls the innermost non-edge one.
# Each widget is bound exactly once to this single handler — no per-canvas
# closures — so N nested regions never multiply the scroll amount.
_SCROLL_CANVASES = []

def _scroll_handler(e, units):
    """Single wheel handler shared by every widget in every scrollable region.
    Walks the parent chain, collects registered canvases innermost-first,
    and scrolls the first one that is not already at its edge."""
    canvases = []
    w = e.widget
    seen = set()
    while w:
        wid = str(w)
        if wid in seen:
            break          # stop if we revisit a node (root loops to itself)
        seen.add(wid)
        if w in _SCROLL_CANVASES:
            canvases.append(w)
        parent_name = w.winfo_parent()
        if not parent_name:
            break          # reached the root
        try:
            w = w.nametowidget(parent_name)
        except Exception:
            break
    direction = -1 if units < 0 else 1
    for c in canvases:
        top, bottom = c.yview()
        at_edge = (top <= 0.0 if direction < 0 else bottom >= 1.0)
        if not at_edge:
            c.yview_scroll(units, "units")
            return

def scrollable(parent, bg=PANEL):
    outer  = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, yscrollincrement=20)
    sb     = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=bg)
    win   = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
    # <Configure> handled below alongside _bind_tree

    _SCROLL_CANVASES.append(canvas)
    def _on_destroy(_):
        if canvas in _SCROLL_CANVASES:
            _SCROLL_CANVASES.remove(canvas)

    canvas.bind("<Destroy>", _on_destroy)

    _bound    = set()
    _binding  = [False]   # re-entrancy guard for _bind_tree

    def _bind_one(widget):
        wid = str(widget)
        if wid in _bound:
            return
        _bound.add(wid)
        widget.bind("<MouseWheel>",
                    lambda e: _scroll_handler(e, int(-1 * (e.delta / 120))))
        widget.bind("<Button-4>",
                    lambda e: _scroll_handler(e, -1))
        widget.bind("<Button-5>",
                    lambda e: _scroll_handler(e,  1))

    def _bind_tree(widget):
        _bind_one(widget)
        for child in widget.winfo_children():
            _bind_tree(child)

    def _on_configure(e):
        # Guard against re-entry: binding can itself trigger <Configure>
        if _binding[0]:
            return
        _binding[0] = True
        try:
            _bind_tree(inner)
        finally:
            _binding[0] = False

    _bind_one(canvas)
    inner.bind("<Configure>", lambda e: (
        canvas.configure(scrollregion=canvas.bbox("all")),
        _on_configure(e)
    ))
    _bind_tree(inner)
    return outer, inner

def safe_filename(name):
    """Strip characters not valid in filenames."""
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip() or "character"


def mecha_hp(ms):
    hp = 40

    # Attribute bonuses
    for a in ms.attributes:
        mod = ATTR_MODIFIES.get(a["name"])
        if not mod:
            continue
        if mod["stat"] == "HP":
            hp += int_or(a["level"]) * mod["per_level"]

    # Defect penalties
    for d in ms.defects:
        mod = DEFECT_MODIFIES.get(d["name"])
        if not mod:
            continue
        if mod["stat"] == "HP":
            hp -= int_or(d["level"]) * mod["per_level"]

    return hp



# ─────────────────────────────────────────────────────────────────────────────
#  MECHA STATE  — data for one mecha owned by a character
# ─────────────────────────────────────────────────────────────────────────────

class MechaState:
    """Lightweight data container for one mecha."""
    def __init__(self, notify_cb, char_state=None):
        self._notify = notify_cb
        self._char_state = char_state

        self.name     = tk.StringVar(value="New Mecha")
        self.mp_total = tk.StringVar(value="40")
        self.details  = tk.StringVar(value="")
        self.attributes = []   # same structure as CharacterState.attributes
        self.weapons    = []   # same structure as CharacterState.weapons
        self.defects    = []   # same structure as CharacterState.defects
        for v in [self.name, self.mp_total, self.details]:
            # Mecha name/mp_total/details should mark the character as unsaved
            if char_state and hasattr(char_state, '_on_var'):
                v.trace_add("write", lambda *_: char_state._on_var())
            else:
                v.trace_add("write", lambda *_: self._notify())

    def mp_spent(self, attr_formula="Default"):
        af      = attr_formula
        attr_mp = sum(attr_cost(a["base_cost"], int_or(a["level"]), af)
                      + int_or(a["modifier"]) for a in self.attributes)
        weap_mp = sum(weapon_cost(w, int_or(w["level"]), int_or(w["modifier"]), af)
                      for w in self.weapons)
        def_mp  = sum(attr_cost(d["base_cost"], int_or(d["level"]), "Default")
                      + int_or(d["modifier"]) for d in self.defects)
        return attr_mp + weap_mp - def_mp

    def to_dict(self):
        return {
            "name":     self.name.get(),
            "mp_total": self.mp_total.get(),
            "details":  self.details.get(),
            "attributes": [
                {"name": a["name"], "base_cost": a["base_cost"],
                 "level": a["level"].get(), "desc": a["desc"].get(),
                 "modifier": a["modifier"].get()}
                for a in self.attributes
            ],
            "weapons": [
                {"name": w["name"].get(), "level": w["level"].get(),
                 "modifier": w["modifier"].get(), "gear": w["gear"].get(),
                 "desc": w["desc"].get(),
                 "advantages": list(w["advantages"]),
                 "defects":    list(w["defects"])}
                for w in self.weapons
            ],
            "defects": [
                {"name": d["name"], "base_cost": d["base_cost"],
                 "level": d["level"].get(), "desc": d["desc"].get(),
                 "modifier": d["modifier"].get()}
                for d in self.defects
            ],
        }

    def from_dict(self, data):
        self.name.set(data.get("name", "New Mecha"))
        self.mp_total.set(data.get("mp_total", "40"))
        self.details.set(data.get("details", ""))

        def _norm(lst):
            out = []
            for e in lst:
                if isinstance(e, str):    out.append((e, 1))
                elif isinstance(e, list): out.append(tuple(e))
                else:                     out.append(e)
            return out

        self.attributes.clear()
        for a in data.get("attributes", []):
            self.attributes.append({
                "name":      a["name"], "base_cost": a["base_cost"],
                "level":     tk.StringVar(value=str(a.get("level", "1"))),
                "desc":      tk.StringVar(value=a.get("desc", "")),
                "modifier":  tk.StringVar(value=str(a.get("modifier", "0"))),
            })
        self.weapons.clear()
        for w in data.get("weapons", []):
            self.weapons.append({
                "name":       tk.StringVar(value=w.get("name", "")),
                "level":      tk.StringVar(value=str(w.get("level", "1"))),
                "modifier":   tk.StringVar(value=str(w.get("modifier", "0"))),
                "gear":       tk.BooleanVar(value=w.get("gear", False)),
                "desc":       tk.StringVar(value=w.get("desc", "")),
                "advantages": _norm(w.get("advantages", [])),
                "defects":    _norm(w.get("defects", [])),
            })
        self.defects.clear()
        for d in data.get("defects", []):
            self.defects.append({
                "name":      d["name"], "base_cost": d["base_cost"],
                "level":     tk.StringVar(value=str(d.get("level", "1"))),
                "desc":      tk.StringVar(value=d.get("desc", "")),
                "modifier":  tk.StringVar(value=str(d.get("modifier", "0"))),
            })

# ─────────────────────────────────────────────────────────────────────────────
#  CHARACTER STATE  — all data for one character, no widgets
# ─────────────────────────────────────────────────────────────────────────────

class CharacterState:
    """
    Holds all Tk variables for one character.
    `notify` is a callable the CharacterTab sets so state changes can
    propagate back up to refresh labels / status bar.
    """
    def __init__(self, notify_cb):
        self._notify = notify_cb

        self.char_name     = tk.StringVar(value="New Character")
        self.attr_formula  = tk.StringVar(value="Default")
        self.cp_total     = tk.StringVar(value="20")
        self.stat_formula = tk.StringVar(value="Default")
        self.body         = tk.StringVar(value="1")
        self.mind         = tk.StringVar(value="1")
        self.soul         = tk.StringVar(value="1")
        self.hp_mod       = tk.StringVar(value="0")
        self.ep_mod       = tk.StringVar(value="0")
        self.acv_mod      = tk.StringVar(value="0")
        self.dcv_mod      = tk.StringVar(value="0")
        self.sv_mod       = tk.StringVar(value="0")
        self.char_details = tk.StringVar(value="")
        self.equip_notes  = tk.StringVar(value="")

        self.attributes = []
        self.weapons    = []
        self.defects    = []
        self.mechas     = []   # list of MechaState
        self._undo_stack = []  # list of (list_ref, index, item_copy)

        self.sp_total      = tk.StringVar(value="20")
        self.skill_setting = tk.StringVar(value=SETTINGS[0])
        self.skill_levels  = {k: tk.IntVar(value=0) for k in SKILLS}
        self.skill_descs   = {k: tk.StringVar(value="") for k in SKILLS}
        self.skill_mods    = {k: tk.IntVar(value=0) for k in SKILLS}
        self.combat_levels = {k: tk.IntVar(value=0) for k in COMBAT_SKILLS}
        self.combat_descs  = {k: tk.StringVar(value="") for k in COMBAT_SKILLS}
        self.combat_mods   = {k: tk.IntVar(value=0) for k in COMBAT_SKILLS}

        watched = (
            [self.char_name, self.cp_total, self.stat_formula, self.attr_formula,
             self.body, self.mind, self.soul,
             self.hp_mod, self.ep_mod, self.acv_mod, self.dcv_mod, self.sv_mod,
             self.sp_total, self.skill_setting]
            + list(self.skill_levels.values())
            + list(self.skill_descs.values())
            + list(self.skill_mods.values())
            + list(self.combat_levels.values())
            + list(self.combat_descs.values())
            + list(self.combat_mods.values())
        )
        self._unsaved = False
        for v in watched:
            v.trace_add("write", self._on_var)
        
        # For char_details and equip_notes, use a separate callback that checks for real changes
        self._last_char_details_saved = ""
        self._last_equip_notes_saved = ""
        self.char_details.trace_add("write", self._on_char_details_change)
        self.equip_notes.trace_add("write", self._on_equip_notes_change)

    def _on_var(self, *_):
        self._unsaved = True
        self._notify()

    def _on_char_details_change(self, *_):
        """Only mark unsaved if char_details actually changed since last save."""
        if self.char_details.get() != self._last_char_details_saved:
            self._unsaved = True
            self._notify()

    def _on_equip_notes_change(self, *_):
        """Only mark unsaved if equip_notes actually changed since last save."""
        if self.equip_notes.get() != self._last_equip_notes_saved:
            self._unsaved = True
            self._notify()

    def mark_clean(self):
        self._unsaved = False
        # Update tracked values for char_details and equip_notes to current state
        self._last_char_details_saved = self.char_details.get()
        self._last_equip_notes_saved = self.equip_notes.get()
        self._notify()   # will call _update_tab_label via _refresh_status → notify chain

    def push_undo(self, list_ref, idx, item):
        """Remember one deleted item so Ctrl+Z can restore it."""
        self._undo_stack.append((list_ref, idx, item))
        if len(self._undo_stack) > 20:
            self._undo_stack.pop(0)

    def pop_undo(self):
        """Restore the last deleted item; return True if something was restored."""
        if not self._undo_stack:
            return False
        list_ref, idx, item = self._undo_stack.pop()
        list_ref.insert(idx, item)
        return True

    # ── Computed values ────────────────────────────────────────────────────
    def derived(self):
        b   = int_or(self.body)
        m   = int_or(self.mind)
        s   = int_or(self.soul)
        acv = math.floor((b + s + m) / 3) + int_or(self.acv_mod)
        dcv = 0
        hp  = 0
        ep  = 0
        sv  = 0
        # Attribute bonuses
        acv_bonus = 0
        sp_bonus = 0
        for a in self.attributes:
            mod = ATTR_MODIFIES.get(a["name"])
            if not mod: continue
            lv = int_or(a["level"])
            stat, per_lv = mod["stat"], mod["per_level"]
            if   stat == "CV":  acv       += lv * per_lv
            elif stat == "ACV": acv_bonus += lv * per_lv
            elif stat == "DCV": dcv       += lv * per_lv
            elif stat == "HP":  hp        += lv * per_lv
            elif stat == "EP":  ep        += lv * per_lv
            elif stat == "SP":  sp_bonus  += lv * per_lv
            elif stat == "SV":  sv        += lv * per_lv
        # Defect penalties
        for d in self.defects:
            mod = DEFECT_MODIFIES.get(d["name"])
            if not mod: continue
            lv = int_or(d["level"])
            stat, per_lv = mod["stat"], mod["per_level"]
            if   stat == "CV":  acv       -= lv * per_lv
            elif stat == "ACV": acv_bonus -= lv * per_lv
            elif stat == "DCV": dcv       -= lv * per_lv
            elif stat == "HP":  hp        -= lv * per_lv
            elif stat == "EP":  ep        -= lv * per_lv
            elif stat == "SP":  sp_bonus  -= lv * per_lv
            elif stat == "SV":  sv        -= lv * per_lv
        # Calculate the relevant values
        hp  += (b + s) * 5 + int_or(self.hp_mod)
        ep  += (m + s) * 5 + int_or(self.ep_mod)
        dcv += acv - 2 + int_or(self.dcv_mod)
        acv += acv_bonus
        sv  += math.floor(hp / 5) + int_or(self.sv_mod)
        return {"ACV": acv, "DCV": dcv, "HP": hp, "EP": ep, "SV": sv,
                "Body": b, "Mind": m, "Soul": s, "SP_bonus": sp_bonus}

    def sp_total_effective(self, derived_cache=None):
        """SP budget including Highly Skilled bonus.
        Pass a pre-computed derived() dict to avoid calling it twice.
        """
        d = derived_cache if derived_cache is not None else self.derived()
        return int_or(self.sp_total) + d.get("SP_bonus", 0)

    def cp_spent(self):
        fn = STAT_FORMULAS.get(
            self.stat_formula.get(),
            _formula_default or next(iter(STAT_FORMULAS.values()))
        )

        af = self.attr_formula.get()
        if af not in _attr_formula_fns:
            af = "Default"
        stat_cp = sum(fn(int_or(v)) for v in [self.body, self.mind, self.soul])
        attr_cp = sum(attr_cost(a["base_cost"], int_or(a["level"]), af) + int_or(a["modifier"])
                      for a in self.attributes)
        weap_cp = sum(weapon_cost(w, int_or(w["level"]), int_or(w["modifier"]), af)
                      for w in self.weapons)
        def_cp  = sum(attr_cost(d["base_cost"], int_or(d["level"]), "Default") + int_or(d["modifier"])
                      for d in self.defects)
        return stat_cp + attr_cp + weap_cp - def_cp

    def sp_spent(self):
        setting = self.skill_setting.get()
        total   = 0
        for name, var in self.skill_levels.items():
            lv = int_or(var)
            if lv > 0:
                cost = lv * SKILLS[name].get(setting, 0)
                mod = int_or(self.skill_mods[name])
                total += cost + mod
        for name, var in self.combat_levels.items():
            lv = int_or(var)
            if lv > 0:
                cost = lv * COMBAT_SKILLS[name].get(setting, 0)
                mod = int_or(self.combat_mods[name])
                total += cost + mod
        return total

    # ── Serialise ──────────────────────────────────────────────────────────
    def to_dict(self):
        return {
            "name":          self.char_name.get(),
            "cp_total":      self.cp_total.get(),
            "stat_formula":  self.stat_formula.get(),
            "attr_formula":  self.attr_formula.get(),
            "body":          self.body.get(),
            "mind":          self.mind.get(),
            "soul":          self.soul.get(),
            "hp_mod":        self.hp_mod.get(),
            "ep_mod":        self.ep_mod.get(),
            "acv_mod":       self.acv_mod.get(),
            "dcv_mod":       self.dcv_mod.get(),
            "sv_mod":        self.sv_mod.get(),
            "sp_total":      self.sp_total.get(),
            "char_details":  self.char_details.get(),
            "equip_notes":   self.equip_notes.get(),
            "skill_setting": self.skill_setting.get(),
            "skill_levels":  {k: v.get() for k, v in self.skill_levels.items()},
            "skill_descs":   {k: v.get() for k, v in self.skill_descs.items()},
            "skill_mods":    {k: v.get() for k, v in self.skill_mods.items()},
            "combat_levels": {k: v.get() for k, v in self.combat_levels.items()},
            "combat_descs":  {k: v.get() for k, v in self.combat_descs.items()},
            "combat_mods":   {k: v.get() for k, v in self.combat_mods.items()},
            "attributes": [
                {"name": a["name"], "base_cost": a["base_cost"],
                 "level": a["level"].get(), "desc": a["desc"].get(),
                 "modifier": a["modifier"].get()}
                for a in self.attributes
            ],
            "weapons": [
                {"name": w["name"].get(), "level": w["level"].get(),
                 "modifier": w["modifier"].get(), "gear": w["gear"].get(),
                 "desc": w["desc"].get(),
                 "advantages": w["advantages"], "defects": w["defects"]}
                for w in self.weapons
            ],
            "defects": [
                {"name": d["name"], "base_cost": d["base_cost"],
                 "level": d["level"].get(), "desc": d["desc"].get(),
                 "modifier": d["modifier"].get()}
                for d in self.defects
            ],
            "mechas": [m.to_dict() for m in self.mechas],
        }

    # ── Deserialise ────────────────────────────────────────────────────────
    def from_dict(self, data):
        for attr, key, default in [
            ("char_name",    "name",          "New Character"),
            ("cp_total",     "cp_total",      "30"),
            ("stat_formula", "stat_formula",  "Default"),
            ("attr_formula", "attr_formula",  "Default"),
            ("body",         "body",          "4"),
            ("mind",         "mind",          "4"),
            ("soul",         "soul",          "4"),
            ("hp_mod",       "hp_mod",        "0"),
            ("ep_mod",       "ep_mod",        "0"),
            ("acv_mod",      "acv_mod",       "0"),
            ("dcv_mod",      "dcv_mod",       "0"),
            ("sv_mod",       "sv_mod",        "0"),
            ("sp_total",     "sp_total",      "30"),
            ("char_details",  "char_details",  ""),
            ("equip_notes",   "equip_notes",   ""),
            ("skill_setting","skill_setting", SETTINGS[0]),
        ]:
            getattr(self, attr).set(data.get(key, default))

        for k, v in data.get("skill_levels",  {}).items():
            if k in self.skill_levels:  self.skill_levels[k].set(v)
        for k, v in data.get("skill_descs",   {}).items():
            if k in self.skill_descs:   self.skill_descs[k].set(v)
        for k, v in data.get("skill_mods",    {}).items():
            if k in self.skill_mods:    self.skill_mods[k].set(v)
        for k, v in data.get("combat_levels", {}).items():
            if k in self.combat_levels: self.combat_levels[k].set(v)
        for k, v in data.get("combat_descs",  {}).items():
            if k in self.combat_descs:  self.combat_descs[k].set(v)
        for k, v in data.get("combat_mods",   {}).items():
            if k in self.combat_mods:   self.combat_mods[k].set(v)

        self.attributes.clear()
        for a in data.get("attributes", []):
            self.attributes.append({
                "name":      a["name"],
                "base_cost": a["base_cost"],
                "level":     tk.StringVar(value=str(a.get("level", "1"))),
                "desc":      tk.StringVar(value=a.get("desc", "")),
                "modifier":  tk.StringVar(value=str(a.get("modifier", "0"))),
            })

        def _norm_entries(lst):
            """Normalise old string entries to (name, level) tuples."""
            out = []
            for e in lst:
                if isinstance(e, str):   out.append((e, 1))
                elif isinstance(e, list): out.append(tuple(e))
                else:                     out.append(e)
            return out

        self.weapons.clear()
        for w in data.get("weapons", []):
            self.weapons.append({
                "name":       tk.StringVar(value=w.get("name", "")),
                "level":      tk.StringVar(value=str(w.get("level", "1"))),
                "modifier":   tk.StringVar(value=str(w.get("modifier", "0"))),
                "gear":       tk.BooleanVar(value=w.get("gear", False)),
                "desc":       tk.StringVar(value=w.get("desc", "")),
                "advantages": _norm_entries(w.get("advantages", [])),
                "defects":    _norm_entries(w.get("defects", [])),
            })

        self.defects.clear()
        for d in data.get("defects", []):
            self.defects.append({
                "name":      d["name"],
                "base_cost": d["base_cost"],
                "level":     tk.StringVar(value=str(d.get("level", "1"))),
                "desc":      tk.StringVar(value=d.get("desc", "")),
                "modifier":  tk.StringVar(value=str(d.get("modifier", "0"))),
            })
        self.mechas.clear()
        for md in data.get("mechas", []):
            ms = MechaState(notify_cb=self._notify, char_state=self)
            ms.from_dict(md)
            self.mechas.append(ms)


# ─────────────────────────────────────────────────────────────────────────────
#  CHARACTER TAB  — one independent character editor inside the notebook
# ─────────────────────────────────────────────────────────────────────────────

class CharacterTab(tk.Frame):
    """
    A self-contained editor. Owns a CharacterState and all pages.
    `app` is the root BESMApp, used only to update the tab label and
    the global status bar.
    """
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app   = app
        self.state = CharacterState(notify_cb=self._update_all)
        self._current_page = 0
        self.tab_label_var = tk.StringVar(value="New Character")
        # Listen to name changes to relabel the tab
        self.state.char_name.trace_add("write", self._on_name_change)
        self.state.attr_formula.trace_add("write", self._on_attr_formula_change)
        self._build()

    def _build(self):
        self._build_inner_nav()
        self._build_pages()
        self._show_page(0)
        self._update_all()   # populate derived values, CP costs and status on first render

    # ── Inner nav (page switcher + save/load for THIS character) ──────────
    def _build_inner_nav(self):
        nav = tk.Frame(self, bg=PANEL)
        nav.pack(side="top", fill="x")

        io = tk.Frame(nav, bg=PANEL)
        io.pack(side="left", padx=4)
        self._io_btns = []
        for label_key, fallback, cmd in [
            ("btn_save",       "💾 Save",       self._save),
            ("btn_load",       "📂 Load",       self._load),
            ("btn_pdf",        "📄 PDF",        self._export_pdf),
            ("btn_save_mecha", "🛡 Save Mecha", self._save_mecha),
            ("btn_load_mecha", "🛠 Load Mecha", self._load_mecha),
        ]:
            b = mk_btn(io, t(label_key, fallback), cmd, bg=CARD, small=True)
            b.pack(side="left", padx=2, pady=5)
            self._io_btns.append((label_key, fallback, b))

        self._status_var = tk.StringVar()
        tk.Label(nav, textvariable=self._status_var,
                 bg=PANEL, fg=TEXT_DIM, font=("Georgia", 9), anchor="w"
                 ).pack(side="left", padx=12)

        self._nav_btns = []
        self._nav_right = tk.Frame(nav, bg=PANEL)
        self._nav_right.pack(side="right", padx=4)
        self._nav_keys = ["page_core", "page_attrs", "page_defects",
                          "page_skills", "page_mecha", "page_summary"]
        self._nav_fallbacks = ["① Core", "② Attr & Weapons", "③ Defects",
                               "④ Skills", "⑤ Mecha", "⑥ Summary"]
        for i, (key, fallback) in enumerate(zip(self._nav_keys, self._nav_fallbacks)):
            b = tk.Button(self._nav_right, text=t(key, fallback),
                          font=("Georgia", 9, "bold"),
                          bg=NAV_INACT, fg=TEXT_DIM, relief="flat",
                          activebackground=NAV_ACT, activeforeground="white",
                          padx=8, pady=6, cursor="hand2",
                          command=lambda i=i: self._show_page(i))
            b.pack(side="left", padx=2, pady=3)
            self._nav_btns.append(b)

    # ── Pages ─────────────────────────────────────────────────────────────
    def _build_pages(self):
        self._container = tk.Frame(self, bg=BG)
        self._container.pack(fill="both", expand=True)
        s = self.state
        self._pages = [
            Page1(self._container, s),
            Page2(self._container, s),
            Page3(self._container, s),
            Page4(self._container, s),
            Page5Mecha(self._container, s),
            Page6Summary(self._container, s),
        ]

    def _show_page(self, idx):
        self._current_page = idx
        for p in self._pages:
            p.place_forget()
        self._pages[idx].place(relx=0, rely=0, relwidth=1, relheight=1)
        for i, b in enumerate(self._nav_btns):
            b.config(bg=NAV_ACT if i == idx else NAV_INACT,
                     fg="white" if i == idx else TEXT_DIM)
        if idx == 5:
            self._pages[5].refresh()
        if idx == 4:
            self._pages[4].on_show()

    def _rebuild_nav_labels(self):
        """Update IO button text and nav tab text after a language change."""
        for label_key, fallback, btn in self._io_btns:
            btn.config(text=t(label_key, fallback))
        for btn, key, fallback in zip(self._nav_btns, self._nav_keys, self._nav_fallbacks):
            btn.config(text=t(key, fallback))

    # ── Update ────────────────────────────────────────────────────────────
    def _update_all(self):
        if not hasattr(self, "_pages"):
            return
        self._pages[0].refresh()
        self._pages[3].refresh_all()
        if self._current_page == 5:
            self._pages[5].refresh()
        self._refresh_status()

    def notify_change(self):
        self._update_all()

    def _refresh_status(self):
        s    = self.state
        cp_s = s.cp_spent()
        cp_t = int_or(s.cp_total)
        d    = s.derived()
        self._update_tab_label()
        self._status_var.set(
            f"{t('label_cp_status','CP:')} {cp_s}/{cp_t} ({t('status_ok','OK') if cp_s<=cp_t else t('status_over','OVER')})"
        )

    def _export_pdf(self):
        name = self.state.char_name.get()
        path = filedialog.asksaveasfilename(
            initialfile=safe_filename(name) + ".pdf",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
            title="Export Character Sheet")
        if not path: return
        try:
            export_pdf(self.state, path)
            messagebox.showinfo("Exported", f"Sheet saved:\n{path}")
        except FileNotFoundError as e:
            messagebox.showerror("Template missing", str(e))
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def undo(self, _event=None):
        if not self.state.pop_undo():
            return
        # Rebuild whichever list was affected
        self._pages[1].rebuild_lists()
        self._pages[1]._weap_list.rebuild()
        self._pages[2].rebuild_list()
        if hasattr(self._pages[4], 'rebuild_active'):
            self._pages[4].rebuild_active()
        self._update_all()
        # Mark the character as modified since undo changed something
        self.state._notify()

    def _on_name_change(self, *_):
        self._update_tab_label()
        self.app.update_tab_label(self)

    def _update_tab_label(self):
        name = self.state.char_name.get() or "Unnamed"
        dot  = " •" if self.state._unsaved else ""
        self.tab_label_var.set(name + dot)

    def _on_attr_formula_change(self, *_):
        if not hasattr(self, "_pages"):
            return
        self._pages[1].rebuild_lists()
        self._pages[2].rebuild_list()
        if hasattr(self._pages[4], "rebuild_active"):
            self._pages[4].rebuild_active()
        if hasattr(self._pages[1], '_weap_list'):
            self._pages[1]._weap_list.notify_formula_change()
        self._refresh_status()

    # ── Save / Load ────────────────────────────────────────────────────────
    def _save(self):
        char_name  = self.state.char_name.get()
        default_fn = safe_filename(char_name) + ".json"
        path = filedialog.asksaveasfilename(
            initialdir=_default_dir(CHARS_DIR),
            initialfile=default_fn,
            defaultextension=".json",
            filetypes=[("BESM Character", "*.json"), ("All files", "*.*")],
            title="Save Character")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, indent=2)
            self.state.mark_clean()
            messagebox.showinfo("Saved", f"Character saved:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save:\n{e}")

    def _load(self):
        path = filedialog.askopenfilename(
            initialdir=_default_dir(CHARS_DIR),
            filetypes=[("BESM Character", "*.json"), ("All files", "*.*")],
            title="Load Character")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load:\n{e}")
            return
        # Temporarily suppress notifications while applying bulk state
        # to avoid repeated rebuilds (slow when many trace callbacks/widgets exist).
        old_notify = getattr(self.state, '_notify', None)
        try:
            self.state._notify = lambda *a, **k: None
            self.state.from_dict(data)
            # perform UI rebuilds once while notifications are suppressed
            self._pages[1].rebuild_lists()
            self._pages[2].rebuild_list()
            self._pages[3].rebuild_all()
            self._pages[4].rebuild_all_mechas()
        finally:
            # restore original notify and run a single unified update
            if old_notify is not None:
                self.state._notify = old_notify
        self._update_all()
        self.state.mark_clean()
        messagebox.showinfo("Loaded", f"Character loaded:\n{path}")

    # ── Mecha import/export ──────────────────────────────────────────────
    def _save_mecha(self):
        page = self._pages[4]
        idx = getattr(page, '_active_idx', -1)
        if idx < 0 or idx >= len(self.state.mechas):
            messagebox.showinfo("No Mecha", "No mecha selected to save.")
            return
        ms = self.state.mechas[idx]
        default_fn = safe_filename(ms.name.get()) + ".json"
        path = filedialog.asksaveasfilename(
            initialdir=_default_dir(MECHA_DIR),
            initialfile=default_fn,
            defaultextension=".json",
            filetypes=[("BESM Mecha", "*.json"), ("All files", "*.*")],
            title="Save Mecha")
        if not path:
            return
        try:
            # start from a fresh default character rather than the current one
            dummy = CharacterState(notify_cb=lambda *a: None)
            char_template = dummy.to_dict()
            mecha_data = ms.to_dict()
            # overwrite the sections with the mecha's own values
            char_template["attributes"] = mecha_data.get("attributes", [])
            char_template["weapons"]    = mecha_data.get("weapons", [])
            char_template["defects"]    = mecha_data.get("defects", [])
            # mecha has MP but char structure expects cp_total
            char_template["cp_total"] = mecha_data.get("mp_total", "0")
            char_template["skill_setting"] = self.state.to_dict().get("skill_setting", "Action Adventure")
            # use mecha name as character name too
            char_template["name"] = mecha_data.get("name", char_template.get("name",""))
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(char_template, f, indent=2)
            messagebox.showinfo("Saved", f"Mecha saved:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save:\n{e}")

    def _load_mecha(self):
        path = filedialog.askopenfilename(
            initialdir=_default_dir(MECHA_DIR),
            filetypes=[("BESM Mecha", "*.json"), ("All files", "*.*")],
            title="Load Mecha")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load:\n{e}")
            return
        ms = MechaState(notify_cb=self.state._notify, char_state=self.state)
        ms.from_dict(data)
        self.state.mechas.append(ms)
        self._pages[4].rebuild_all_mechas()
        self._update_all()
        messagebox.showinfo("Loaded", f"Mecha imported:\n{path}")




# ─────────────────────────────────────────────────────────────────────────────
#  PDF EXPORT  — procedural, via reportlab
# ─────────────────────────────────────────────────────────────────────────────

def export_pdf(state, out_path):
    """Generate a character sheet PDF procedurally using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as _rl_canvas
        from reportlab.lib.colors import HexColor, black, white
        from reportlab.lib.utils import ImageReader
    except ImportError:
        raise RuntimeError("reportlab not installed — run: pip install reportlab")

    import math as _math, os as _os

    PW, PH = A4
    M  = 12 * mm
    GR =  4 * mm

    # ── Colours (print-friendly) ──────────────────────────────────────────
    C_YELLOW = HexColor("#fffcd6")
    C_BLUE   = HexColor("#c7ebfc")
    C_GREEN  = HexColor("#d8e8d8")
    C_DIM    = HexColor("#555555")
    C_RULE   = HexColor("#999999")
    C_ROWALT = HexColor("#f0f0f0")
    C_HDRBG  = HexColor("#1a1a2e")
    C_SECTBG = HexColor("#344060")
    C_ACCENT = HexColor("#c0392b")
    C_GREY2  = HexColor("#dddddd")
    C_GREY3  = HexColor("#888888")

    # ── Logo ──────────────────────────────────────────────────────────────
    _logo_candidates = [
        str(_bundle_dir() / "BESM2_Retro_logo_dtrpg_250px.png"),
        str(_exe_dir()    / "BESM2_Retro_logo_dtrpg_250px.png"),
        _os.path.join(_os.getcwd(), "BESM2_Retro_logo_dtrpg_250px.png"),
    ]
    _logo_path = next((p for p in _logo_candidates if _os.path.exists(p)), None)
    LOGO_W = 36 * mm
    LOGO_H = LOGO_W / 2.5   # 250x100 aspect

    # ── Drawing helpers ───────────────────────────────────────────────────
    def _rr(c, x, y, w, h, fill, stroke=None, lw=0.4):
        c.setFillColor(fill)
        if stroke:
            c.setStrokeColor(stroke); c.setLineWidth(lw)
            c.rect(x, y, w, h, fill=1, stroke=1)
        else:
            c.rect(x, y, w, h, fill=1, stroke=0)

    def _t(c, x, y, s, font="Helvetica", size=8, color=black, align="left"):
        c.setFont(font, size); c.setFillColor(color)
        if   align == "center": c.drawCentredString(x, y, str(s))
        elif align == "right":  c.drawRightString(x, y, str(s))
        else:                   c.drawString(x, y, str(s))

    def _section(c, x, y, w, label):
        h = 5 * mm
        _rr(c, x, y - h, w, h, C_SECTBG)
        _t(c, x + 2, y - h + 1.5*mm, label.upper(), "Helvetica-Bold", 7.5, white)
        return y - h - 1*mm

    # ── Adv/def string: only show xN when N > 1 ──────────────────────────
    def _adv_str(entries):
        seen = {}
        for e in entries:
            n, lv = (e[0], e[1]) if isinstance(e, (list, tuple)) else (e, 1)
            seen[n] = seen.get(n, 0) + lv
        parts = [display_name(n) if total == 1 else f"{display_name(n)} x{total}"
                 for n, total in seen.items()]
        return ", ".join(parts) if parts else "\u2014"

    # ── Header ────────────────────────────────────────────────────────────
    HEADER_H = 18 * mm
    LOGO_PAD = (HEADER_H - LOGO_H) / 2

    def _draw_header(c, page, total_pages, show_cp_sp=False):
        _rr(c, 0, PH - HEADER_H, PW, HEADER_H, C_HDRBG)
        _rr(c, 0, PH - HEADER_H - 0.8*mm, PW, 0.8*mm, C_ACCENT)
        if _logo_path:
            c.drawImage(ImageReader(_logo_path),
                        M, PH - HEADER_H + LOGO_PAD,
                        width=LOGO_W, height=LOGO_H, mask="auto")
        cx = M + LOGO_W + 5*mm
        cw = PW - cx - M
        band_h = HEADER_H - 2*mm
        by = PH - HEADER_H + 1*mm
        if show_cp_sp:
            name_w = cw * 0.50
            cp_w   = (cw - name_w - 2*mm) / 2
        else:
            name_w = cw
            cp_w   = 0
        _rr(c, cx, by, name_w - 1, band_h, C_YELLOW, C_RULE, 0.4)
        _t(c, cx + 2, by + band_h - 3.5*mm, t("pdf_char_name","Character Name"), "Helvetica", 6, C_DIM)
        _t(c, cx + name_w/2, by + 3*mm,
           state.char_name.get() or "Unnamed",
           "Helvetica-Bold", 10, black, "center")
        if show_cp_sp:
            cp_t = int_or(state.cp_total)
            cp_s = state.cp_spent()
            sp_t = state.sp_total_effective()
            sp_s = state.sp_spent()
            bx = cx + name_w + 1*mm
            for label, val in [(t("pdf_char_points","Character Points"), f"{cp_s}/{cp_t}"),
                                (t("pdf_skill_points","Skill Points"),     f"{sp_s}/{sp_t}")]:
                _rr(c, bx, by, cp_w, band_h, C_YELLOW, C_RULE, 0.4)
                _t(c, bx + 2, by + band_h - 3.5*mm, label, "Helvetica", 6, C_DIM)
                _t(c, bx + cp_w/2, by + 3*mm, val,
                   "Helvetica-Bold", 9, black, "center")
                bx += cp_w + 1*mm
        _t(c, PW - M, 6*mm, f"{t('pdf_page','Page')} {page} {t('pdf_of','/')} {total_pages}",
           "Helvetica", 7, C_GREY3, "right")

    CONTENT_TOP = PH - HEADER_H - 2*mm
    DET_H       = 14*mm
    EQUIP_H     = 22*mm
    MECHA_DET_H = 12*mm

    # ── Helpers ───────────────────────────────────────────────────────────
    def _draw_boxed_text(c, x, y_top, w, h, text,
                         font="Helvetica", size=7.5, color=black):
        """Render multi-line *text* inside a box. y_top is the top edge of
        the rectangle; the box extends downward by *h*.  Text is word-wrapped
        to fit width *w* and truncated if it exceeds the available height.
        Existing newlines are preserved as paragraph breaks.
        """
        if not text:
            return
        # break into paragraphs on newline, then wrap each paragraph
        paras = text.replace("\r", "").split("\n")
        lines = []
        lh = 3.5 * mm
        for para in paras:
            words = para.split()
            if not words:
                # blank line
                lines.append("")
                continue
            cur = ""
            for word in words:
                test = (cur + " " + word).strip()
                if c.stringWidth(test, font, size) <= w - 4:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = word
            if cur:
                lines.append(cur)
        # draw lines with simple line spacing, truncating at box height
        max_lines = int(h / lh)
        for i, line in enumerate(lines[:max_lines]):
            _t(c, x + 2, y_top - 4*mm - i * lh, line, font, size, color)

    # ── Character details box ─────────────────────────────────────────────
    def _draw_char_details(c, y):
        y2 = _section(c, M, y, PW - 2*M, t("pdf_char_details","Character Details"))
        _rr(c, M, y2 - DET_H, PW - 2*M, DET_H, C_YELLOW, C_RULE, 0.4)
        _draw_boxed_text(c, M, y2, PW - 2*M, DET_H,
                         state.char_details.get())
        return y2 - DET_H - 3*mm

    # ── Stats row ─────────────────────────────────────────────────────────
    def _draw_stats(c, y, d):
        sh = 16*mm; fw = PW - 2*M; sw = fw * 0.12
        bx = M
        for label, val, col in [(t("pdf_body","BODY"), d["Body"], C_BLUE),
                                  (t("pdf_mind","MIND"), d["Mind"], C_BLUE),
                                  (t("pdf_soul","SOUL"), d["Soul"], C_BLUE)]:
            _rr(c, bx, y - sh, sw - 1, sh, col, C_RULE, 0.4)
            _t(c, bx + sw/2, y - 4.5*mm,   label, "Helvetica",      6,  C_DIM,  "center")
            _t(c, bx + sw/2, y - sh + 4*mm, val,  "Helvetica-Bold", 16, black,  "center")
            bx += sw + 1*mm
        bx += 4*mm
        dw = (fw - 3*sw - 3*mm - 4*mm) / 5 - 0.8*mm
        for label, val in [(t("pdf_hp","HP"), d["HP"]), (t("pdf_ep","EP"), d["EP"]), (t("pdf_sv","SV"), d["SV"]),
                            (t("pdf_acv","ACV"), d["ACV"]), (t("pdf_dcv","DCV"), d["DCV"])]:
            _rr(c, bx, y - sh, dw, sh, C_GREEN, C_RULE, 0.4)
            _t(c, bx + dw/2, y - 4.5*mm,   label, "Helvetica",      6,  C_DIM,  "center")
            _t(c, bx + dw/2, y - sh + 4*mm, val,  "Helvetica-Bold", 12, black,  "center")
            bx += dw + 0.8*mm
        return y - sh - 3*mm

    # ── Attribute / defect table ──────────────────────────────────────────
    def _draw_attr_table(c, x, y, w, rows, col3="CP"):
        rh = 5*mm
        COL = [w*0.43, w*0.09, w*0.13, w*0.35]
        _rr(c, x, y - rh, w, rh, C_GREY2)
        c.setStrokeColor(C_RULE); c.setLineWidth(0.3)
        c.line(x, y - rh, x + w, y - rh)
        cx = x
        for hdr, cw in zip([t("pdf_col_name","Name"), t("label_lv_col","Lv"), col3, t("pdf_col_notes","Notes")], COL):
            _t(c, cx + 1, y - 3.5*mm, hdr, "Helvetica-Bold", 6.5, C_DIM)
            cx += cw
        y -= rh
        for i, (name, lv, cost, desc) in enumerate(rows):
            bg = C_ROWALT if i % 2 else white
            _rr(c, x, y - rh, w, rh, bg)
            cx = x
            for val, cw in zip([name, str(lv), str(cost), desc or ""], COL):
                s2 = str(val)
                while s2 and c.stringWidth(s2, "Helvetica", 7.5) > cw - 3:
                    s2 = s2[:-1]
                _t(c, cx + 1, y - 3.8*mm, s2, "Helvetica", 7.5, black)
                cx += cw
            c.setStrokeColor(C_RULE); c.setLineWidth(0.2)
            c.line(x, y - rh, x + w, y - rh)
            y -= rh
        return y - 2*mm

    # ── Weapon table ──────────────────────────────────────────────────────
    def _draw_weapon_table(c, x, y, w, weap_list, unit="CP"):
        af_formula = state.attr_formula.get()
        rh1 = 5*mm; rh2 = 4*mm
        COL = [w*0.28, w*0.06, w*0.09, w*0.08, w*0.05]
        dx  = sum(COL); dw = w - dx - 2
        _rr(c, x, y - rh1, w, rh1, C_GREY2)
        c.setStrokeColor(C_RULE); c.setLineWidth(0.3)
        c.line(x, y - rh1, x + w, y - rh1)
        cx = x
        for hdr, cw in zip([t("pdf_col_name","Name"), t("label_lv_col","Lv"), unit, t("label_dmg_abbr","Dmg"), t("pdf_col_gm","G/M")], COL):
            _t(c, cx + 1, y - 3.5*mm, hdr, "Helvetica-Bold", 6.5, C_DIM)
            cx += cw
        _t(c, x + dx + 1, y - 3.5*mm, t("pdf_col_desc","Desc"), "Helvetica-Bold", 6.5, C_DIM)
        y -= rh1
        for i, weap in enumerate(weap_list):
            lv      = int_or(weap["level"])
            mod     = int_or(weap["modifier"])
            cost    = weapon_cost(weap, lv, mod, af_formula)
            dmg     = weapon_damage(weap, lv)
            is_gear = weap["gear"].get() if hasattr(weap["gear"], "get") \
                      else bool(weap["gear"])
            wname   = weap["name"].get() if hasattr(weap["name"], "get") \
                      else str(weap["name"])
            desc    = weap["desc"].get() if hasattr(weap["desc"], "get") \
                      else str(weap["desc"])
            adv_s   = _adv_str(weap.get("advantages", []))
            def_s   = _adv_str(weap.get("defects", []))
            bg = C_ROWALT if i % 2 else white
            _rr(c, x, y - rh1 - rh2, w, rh1 + rh2, bg)
            cx = x
            for val, cw in zip([wname, lv, cost, dmg, "✓" if is_gear else " "], COL):
                s2 = str(val)
                while s2 and c.stringWidth(s2, "Helvetica-Bold", 7.5) > cw - 2:
                    s2 = s2[:-1]
                _t(c, cx + 1, y - 3.8*mm, s2, "Helvetica-Bold", 7.5, black)
                cx += cw
            desc2 = desc
            while desc2 and c.stringWidth(desc2, "Helvetica", 7) > dw:
                desc2 = desc2[:-1]
            _t(c, x + dx + 1, y - 3.8*mm, desc2, "Helvetica", 7, C_DIM)
            y -= rh1
            line2 = f"  {t('pdf_adv','Adv:')} {adv_s}   {t('pdf_def','Def:')} {def_s}"
            while line2 and c.stringWidth(line2, "Helvetica-Oblique", 6.5) > w - 4:
                line2 = line2[:-1]
            _t(c, x + 4, y - 2.8*mm, line2, "Helvetica-Oblique", 6.5, C_DIM)
            c.setStrokeColor(C_RULE); c.setLineWidth(0.2)
            c.line(x, y - rh2, x + w, y - rh2)
            y -= rh2
        return y - 2*mm

    # ── Skills block ──────────────────────────────────────────────────────
    def _draw_skills(c, x, y, w):
        d = state.derived()
        setting = state.skill_setting.get()
        purchased = []
        for name, var in state.combat_levels.items():
            lv = var.get()
            if lv > 0:
                base_sp = COMBAT_SKILLS[name].get(setting, 0) * lv
                mod = state.combat_mods[name].get()
                sp = base_sp + mod
                is_atk = COMBAT_SKILLS[name].get("is_attack", True)
                bv     = d["ACV"] if is_atk else d["DCV"]
                btag   = t("label_acv","ACV") if is_atk else t("label_dcv","DCV")
                purchased.append((name, lv, sp,
                                   state.combat_descs[name].get(), True,
                                   lv + bv, btag))
        for name, var in state.skill_levels.items():
            lv = var.get()
            if lv > 0:
                base_sp = SKILLS[name].get(setting, 0) * lv
                mod = state.skill_mods[name].get()
                sp = base_sp + mod
                purchased.append((name, lv, sp,
                                   state.skill_descs[name].get(), False,
                                   None, None))
        if not purchased:
            return y
        rh = 4.5*mm; half = (w - 2*mm) / 2
        col_x = [x, x + half + 2*mm]; col_y = [y, y]
        for i, (name, lv, sp, desc, is_combat, bv_total, btag) in enumerate(purchased):
            ci = i % 2; cy = col_y[ci]; cx2 = col_x[ci]
            bg = C_ROWALT if (i // 2) % 2 else white
            _rr(c, cx2, cy - rh, half, rh, bg)
            fn = "Helvetica-Bold" if is_combat else "Helvetica"
            if is_combat:
                label = f"{display_name(name)}  {t('label_lv_col','Lv')}{lv}  ({sp} {t('pdf_sp','SP')})  = {bv_total} {btag}"
            else:
                label = f"{display_name(name)}  {t('label_lv_col','Lv')}{lv}  ({sp} {t('pdf_sp','SP')})"
            if desc:
                label += f"  \u2014 {desc}"
            while label and c.stringWidth(label, fn, 7) > half - 4:
                label = label[:-1]
            _t(c, cx2 + 2, cy - 3.2*mm, label, fn, 7, black)
            c.setStrokeColor(C_RULE); c.setLineWidth(0.2)
            c.line(cx2, cy - rh, cx2 + half, cy - rh)
            col_y[ci] -= rh
        return min(col_y) - 2*mm

    # ── Height estimators ─────────────────────────────────────────────────
    SECT_H = 6*mm

    def _weap_h(lst):   return (len(lst) * 9 + 5) * mm + 3*mm
    def _skill_h():
        n  = sum(1 for v in state.skill_levels.values()  if v.get() > 0)
        n += sum(1 for v in state.combat_levels.values() if v.get() > 0)
        return _math.ceil(n / 2) * 4.5*mm + 6*mm if n else 0

    def _mecha_block_h(ms):
        col_rows = max(len(ms.attributes), len(ms.defects), 1)
        return ((7 + 1)*mm + MECHA_DET_H + 2*mm
                + SECT_H + (col_rows + 1) * 5*mm + 2*mm
                + SECT_H + (len(ms.weapons) * 9 + 5) * mm + 3*mm)

    # ── Mecha block ───────────────────────────────────────────────────────
    def _draw_mecha(c, y, ms):
        af_formula = state.attr_formula.get()
        col_w = (PW - 2*M - GR) / 2
        lx = M; rx = M + col_w + GR
        mp_s = ms.mp_spent(af_formula)
        mp_t = int_or(ms.mp_total)
        mhp  = mecha_hp(ms)
        # name bar
        bar_h = 7*mm
        _rr(c, M, y - bar_h, PW - 2*M, bar_h, C_HDRBG)
        _t(c, M + 3, y - bar_h + 2*mm,
           f"\u2699  {ms.name.get()}", "Helvetica-Bold", 10, white)
        _t(c, PW - 2*M, y - bar_h + 2*mm,
           f"{t('pdf_mp','MP:')} {mp_s}/{mp_t}   {t('pdf_hp_bar','HP:')} {mhp}",
           "Helvetica", 8, HexColor("#aaaaaa"), "right")
        y -= bar_h + 1*mm
        # mecha details box
        _rr(c, M, y - MECHA_DET_H, PW - 2*M, MECHA_DET_H, C_YELLOW, C_RULE, 0.4)
        det = ms.details.get()
        if det:
            _draw_boxed_text(c, M, y, PW - 2*M, MECHA_DET_H, det)
        y -= MECHA_DET_H + 2*mm
        # attrs + defects
        af_rows, def_rows = [], []
        for a in ms.attributes:
            lv = int_or(a["level"]); mod = int_or(a["modifier"])
            af_rows.append((display_name(a["name"]), lv,
                             attr_cost(a["base_cost"], lv, af_formula) + mod,
                             a["desc"].get()))
        for d in ms.defects:
            lv = int_or(d["level"]); mod = int_or(d["modifier"])
            def_rows.append((display_name(d["name"]), lv,
                              attr_cost(d["base_cost"], lv, "Default") + mod,
                              d["desc"].get()))
        yl = _section(c, lx, y, col_w, t("pdf_mecha_attrs","Mecha Attributes"))
        yr = _section(c, rx, y, col_w, t("pdf_mecha_defects","Mecha Defects"))
        yl = _draw_attr_table(c, lx, yl, col_w, af_rows, col3=t("pdf_col_mp","MP"))
        yr = _draw_attr_table(c, rx, yr, col_w, def_rows, col3=t("pdf_col_refund","Refund"))
        yw = min(yl, yr) - 1*mm
        yw = _section(c, M, yw, PW - 2*M, t("pdf_mecha_weapons","Mecha Weapons"))
        yw = _draw_weapon_table(c, M, yw, PW - 2*M, ms.weapons, unit=t("pdf_col_mp","MP"))
        return yw - 3*mm

    # ── Collect row data ──────────────────────────────────────────────────
    d  = state.derived()
    af = state.attr_formula.get()

    attr_rows = []
    for a in state.attributes:
        lv = int_or(a["level"]); mod = int_or(a["modifier"])
        attr_rows.append((display_name(a["name"]), lv,
                           attr_cost(a["base_cost"], lv, af) + mod,
                           a["desc"].get()))
    def_rows = []
    for a in state.defects:
        lv = int_or(a["level"]); mod = int_or(a["modifier"])
        def_rows.append((display_name(a["name"]), lv,
                          attr_cost(a["base_cost"], lv, "Default") + mod,
                          a["desc"].get()))

    col_w   = (PW - 2*M - GR) / 2
    skill_h = _skill_h()
    weap_h  = _weap_h(state.weapons)

    # how many attr/def rows fit on page 1
    avail_col = (CONTENT_TOP - DET_H - 3*mm - 16*mm - 3*mm
                 - SECT_H - SECT_H - weap_h
                 - SECT_H - skill_h
                 - SECT_H - EQUIP_H - 4*mm)
    rows_fit  = max(1, int(avail_col / (5*mm)))

    attrs_p1 = attr_rows[:rows_fit];  attrs_p2 = attr_rows[rows_fit:]
    defs_p1  = def_rows[:rows_fit];   defs_p2  = def_rows[rows_fit:]
    need_p2  = bool(attrs_p2 or defs_p2)

    # mecha packing
    avail_mecha = CONTENT_TOP - M
    mecha_pages = []
    cur_group = []; cur_used = 0
    for ms in state.mechas:
        h = _mecha_block_h(ms)
        if cur_group and cur_used + h + 4*mm > avail_mecha:
            mecha_pages.append(cur_group)
            cur_group = [ms]; cur_used = h
        else:
            cur_group.append(ms); cur_used += h + 4*mm
    if cur_group:
        mecha_pages.append(cur_group)

    total_pages = 1 + (1 if need_p2 else 0) + len(mecha_pages)

    # ── Draw ──────────────────────────────────────────────────────────────
    c = _rl_canvas.Canvas(out_path, pagesize=A4)
    c.setTitle(f"BESM 2E \u2014 {state.char_name.get()}")
    c.setAuthor("BESM Character Creator")

    # Page 1
    _draw_header(c, 1, total_pages, show_cp_sp=True)
    y = CONTENT_TOP
    y = _draw_char_details(c, y)
    y = _draw_stats(c, y, d)
    y -= 1*mm

    yl = _section(c, M,          y, col_w, t("pdf_attributes","Attributes"))
    yr = _section(c, M+col_w+GR, y, col_w, t("pdf_defects","Defects"))
    yl = _draw_attr_table(c, M,          yl, col_w, attrs_p1, col3=t("pdf_col_cp","CP"))
    yr = _draw_attr_table(c, M+col_w+GR, yr, col_w, defs_p1, col3=t("pdf_col_refund","Refund"))

    yw = min(yl, yr) - 1*mm
    yw = _section(c, M, yw, PW - 2*M, t("pdf_weapons","Weapons"))
    yw = _draw_weapon_table(c, M, yw, PW - 2*M, state.weapons, unit=t("pdf_col_cp","CP"))
    if skill_h > 0:
        yw = _section(c, M, yw, PW - 2*M, t("pdf_skills","Skills"))
        yw = _draw_skills(c, M, yw, PW - 2*M)
    yw -= 1*mm
    yw = _section(c, M, yw, PW - 2*M, t("pdf_equip_notes","Equipment & Adventuring Notes"))
    _rr(c, M, yw - EQUIP_H, PW - 2*M, EQUIP_H, C_GREEN, C_RULE, 0.4)
    _draw_boxed_text(c, M, yw, PW - 2*M, EQUIP_H, state.equip_notes.get())

    # Page 2 — overflow attrs/defs
    page_num = 1
    if need_p2:
        page_num += 1
        c.showPage()
        _draw_header(c, page_num, total_pages)
        y = CONTENT_TOP
        if attrs_p2:
            y2 = _section(c, M, y, col_w, t("pdf_attrs_cont","Attributes (continued)"))
            _draw_attr_table(c, M, y2, col_w, attrs_p2, col3=t("pdf_col_cp","CP"))
        if defs_p2:
            y2 = _section(c, M+col_w+GR, y, col_w, t("pdf_defs_cont","Defects (continued)"))
            _draw_attr_table(c, M+col_w+GR, y2, col_w, defs_p2, col3=t("pdf_col_refund","Refund"))

    # Mecha pages
    for mecha_group in mecha_pages:
        page_num += 1
        c.showPage()
        _draw_header(c, page_num, total_pages)
        y = CONTENT_TOP
        for ms in mecha_group:
            y = _draw_mecha(c, y, ms)

    c.save()



# ─────────────────────────────────────────────────────────────────────────────
#  THE ARSENAL  — standalone weapon library window
# ─────────────────────────────────────────────────────────────────────────────

class ArsenalWindow(tk.Toplevel):
    """
    A persistent top-level window that acts as a weapon library.
    Single-column scrollable list: each weapon is fully editable in-place
    (same style as the character weapon list), with an add-form at the top.
    Weapons can be saved/loaded as a JSON file and copied into the active tab.
    """
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.configure(bg=BG)
        self.geometry("720x760")
        self.minsize(560, 480)

        # Plain-dict weapon storage (no Tk vars at rest — created on rebuild).
        # Each entry: {name, level, modifier, gear, desc, advantages, defects}
        self._weapons     = []
        self._cost_labels = {}
        self._dmg_labels  = {}
        self._pool        = []   # reusable row slots
        self._empty_lbl   = None # "No weapons yet." label

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _refresh_title(self):
        """Update all translated text in the Arsenal window after a language switch."""
        self.title(t("arsenal_title", "⚔  The Arsenal"))
        if hasattr(self, "_title_lbl"):
            self._title_lbl.config(text=t("arsenal_title", "⚔  The Arsenal"))
        if hasattr(self, "_save_btn"):
            self._save_btn.config(text=t("arsenal_btn_save", "💾 Save Arsenal"))
        if hasattr(self, "_load_btn"):
            self._load_btn.config(text=t("arsenal_btn_load", "📂 Load Arsenal"))

        # Rebuild the add-form and list area so all their labels also update.
        # The scrollable inner frame holds: add-form header, form panel,
        # list header, and the list_frame — tear them all down and rebuild.
        for widget in self._inner.winfo_children():
            widget.destroy()
        self._build_add_form()
        self._build_list_area()
        self._rebuild_list()

    # ── Top-level layout ──────────────────────────────────────────────────
    def _build(self):
        # Action bar
        bar = tk.Frame(self, bg=CARD)
        bar.pack(side="top", fill="x")
        self._title_lbl = tk.Label(bar, text=t("arsenal_title", "⚔  The Arsenal"),
                 bg=CARD, fg=ACCENT, font=("Georgia", 12, "bold"), padx=12)
        self._title_lbl.pack(side="left")
        self._save_btn = mk_btn(bar, t("arsenal_btn_save", "💾 Save Arsenal"),
                                self._save, bg=CARD, small=True)
        self._save_btn.pack(side="left", padx=4, pady=4)
        self._load_btn = mk_btn(bar, t("arsenal_btn_load", "📂 Load Arsenal"),
                                self._load, bg=CARD, small=True)
        self._load_btn.pack(side="left", padx=2, pady=4)
        self._status_var = tk.StringVar()
        tk.Label(bar, textvariable=self._status_var, bg=CARD, fg=TEXT_DIM,
                 font=("Georgia", 9)).pack(side="left", padx=12)

        # Single scrollable column for everything (add-form + weapon rows)
        sc_outer, self._inner = scrollable(self, bg=BG)
        sc_outer.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_add_form()
        self._build_list_area()
        self._refresh_title()

    # ── Add-weapon form (always visible at the top of the scroll) ─────────
    def _build_add_form(self):
        hdr = tk.Frame(self._inner, bg=BG)
        hdr.pack(fill="x", pady=(4, 2))
        tk.Label(hdr, text=t("arsenal_new_weapon", "New Weapon"), bg=BG, fg=ACCENT,
                 font=("Georgia", 12, "bold")).pack(side="left", padx=4)

        form = tk.Frame(self._inner, bg=PANEL, pady=8)
        form.pack(fill="x", pady=(0, 8))

        self._nw_name  = tk.StringVar()
        self._nw_level = tk.StringVar(value="1")
        self._nw_mod   = tk.StringVar(value="0")
        self._nw_gear  = tk.BooleanVar(value=False)
        self._nw_desc  = tk.StringVar()
        # Staging dict for the Adv/Def toggle panel
        self._nw_staging = {"advantages": [], "defects": []}

        # Row 0: name
        tk.Label(form, text=t("label_name_add", "Name:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=0, column=0, padx=8, sticky="w", pady=2)
        mk_entry(form, self._nw_name, width=28).grid(
            row=0, column=1, columnspan=5, sticky="ew", padx=4, pady=2)

        # Row 1: level / modifier / gear
        tk.Label(form, text=t("label_level_add", "Level:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=1, column=0, padx=8, sticky="w")
        _nw_lv_sb = mk_int_spinbox(form, self._nw_level, width=4, from_=1, to=20)
        _nw_lv_sb.grid(row=1, column=1, padx=4, sticky="w")
        tk.Label(form, text=t("label_modifier_add", "Modifier:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=1, column=2, padx=4)
        mk_int_spinbox(form, self._nw_mod, width=4, from_=-99, to=99).grid(
            row=1, column=3, padx=4, sticky="w")
        tk.Label(form, text=t("label_gear_colon", "Gear:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=1, column=4, padx=4)
        tk.Checkbutton(form, variable=self._nw_gear, bg=PANEL,
                       selectcolor=CARD, activebackground=PANEL,
                       command=lambda sb=_nw_lv_sb: sb.configure(
                           from_=0 if self._nw_gear.get() else 1)
                       ).grid(row=1, column=5, padx=2)

        # Row 2: desc
        tk.Label(form, text=t("label_desc", "Desc:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=2, column=0, padx=8, sticky="w", pady=2)
        mk_entry(form, self._nw_desc, width=34).grid(
            row=2, column=1, columnspan=5, sticky="ew", padx=4, pady=2)

        # Row 3: Adv/Def toggle button
        adf_frame = tk.Frame(form, bg=PANEL)
        self._nw_adf_frame = adf_frame
        self._nw_adf_open  = False

        def _toggle_adf():
            if self._nw_adf_open:
                self._nw_adf_frame.grid_remove()
                self._nw_adf_open = False
            else:
                build_adv_def_panel(self._nw_adf_frame, self._nw_staging, PANEL, lambda: None)
                self._nw_adf_frame.grid()
                self._nw_adf_open = True
            _upd_adf_btn()

        def _upd_adf_btn():
            wa = weap_adv_weight(self._nw_staging.get("advantages", []))
            wd = weap_def_weight(self._nw_staging.get("defects",    []))
            parts = []
            if wa: parts.append(f"+{wa}")
            if wd: parts.append(f"-{wd}")
            weight_str = "  [" + ", ".join(parts) + "]" if parts else ""
            arrow = "▼" if self._nw_adf_open else "▶"
            if self._nw_adf_open:
                summary = weight_str
            else:
                adv_names = [display_name(e[0] if isinstance(e, (list, tuple)) else e)
                             for e in self._nw_staging.get("advantages", [])]
                def_names = [display_name(e[0] if isinstance(e, (list, tuple)) else e)
                             for e in self._nw_staging.get("defects", [])]
                all_names = adv_names + def_names
                names_str = "  " + ", ".join(all_names) if all_names else ""
                summary = names_str + weight_str
            self._nw_adf_btn.config(
                text=f"{arrow} {t('label_adv_def','Adv/Def')}{summary}")

        self._nw_adf_btn = tk.Button(
            form, font=("Georgia", 8), bg=PANEL, fg=TEXT_DIM,
            relief="flat", cursor="hand2", anchor="w",
            activebackground=PANEL, command=_toggle_adf)
        _upd_adf_btn()
        self._nw_adf_btn.grid(row=3, column=0, columnspan=6,
                               sticky="w", padx=8, pady=(4, 0))
        adf_frame.grid(row=4, column=0, columnspan=6, sticky="ew", padx=8, pady=2)
        adf_frame.grid_remove()

        mk_btn(form, t("arsenal_btn_add", "+ Add to Arsenal"), self._add_weapon).grid(
            row=5, column=0, columnspan=6, pady=8)

    # ── Weapon list header + scrollable rows ──────────────────────────────
    def _build_list_area(self):
        hdr = tk.Frame(self._inner, bg=BG)
        hdr.pack(fill="x", pady=(0, 2))
        tk.Label(hdr, text=t("arsenal_section_title", "Arsenal"), bg=BG, fg=ACCENT,
                 font=("Georgia", 12, "bold")).pack(side="left", padx=4)
        tk.Label(hdr, text=t("arsenal_copy_hint", "— click  ➤  to copy to the active character"),
                 bg=BG, fg=TEXT_DIM, font=("Georgia", 8, "italic")).pack(side="left")

        # Container for weapon rows — rebuilt by _rebuild_list
        self._list_frame = tk.Frame(self._inner, bg=BG)
        self._list_frame.pack(fill="x")

    # ── Add ───────────────────────────────────────────────────────────────
    def _add_weapon(self):
        adv  = list(self._nw_staging.get("advantages", []))
        defs = list(self._nw_staging.get("defects",    []))
        name = self._nw_name.get().strip() or \
               f"{t('arsenal_weapon_default_name', 'Weapon')} {len(self._weapons) + 1}"
        self._weapons.append({
            "name":       name,
            "level":      self._nw_level.get(),
            "modifier":   self._nw_mod.get(),
            "gear":       self._nw_gear.get(),
            "desc":       self._nw_desc.get(),
            "advantages": adv,
            "defects":    defs,
        })
        self._nw_name.set(""); self._nw_level.set("1"); self._nw_mod.set("0")
        self._nw_gear.set(False); self._nw_desc.set("")
        # Reset staging and close the Adv/Def panel
        self._nw_staging["advantages"] = []
        self._nw_staging["defects"]    = []
        if self._nw_adf_open:
            self._nw_adf_frame.grid_remove()
            self._nw_adf_open = False
        self._nw_adf_btn.config(text=f"▶ {t('label_adv_def','Adv/Def')}")
        self._rebuild_list()
        self._set_status(t("arsenal_status_added", 'Added "{name}".').format(name=name))

    # ── Arsenal row pool ─────────────────────────────────────────────────────
    def _make_arsenal_slot(self, idx):
        """Create one reusable weapon row with all sub-widgets."""
        bg  = CARD if idx % 2 == 0 else PANEL
        row = tk.Frame(self._list_frame, bg=bg, pady=4)

        r0 = tk.Frame(row, bg=bg); r0.pack(fill="x")
        name_entry = mk_entry(r0, tk.StringVar(), width=18, font=("Georgia", 9))
        name_entry.pack(side="left", padx=(6, 2))
        up_btn = mk_btn(r0, "▲", lambda: None, bg=CARD, small=True)
        up_btn.pack(side="left", padx=1)
        dn_btn = mk_btn(r0, "▼", lambda: None, bg=CARD, small=True)
        dn_btn.pack(side="left", padx=(1, 4))
        cl = tk.Label(r0, text="", bg=bg, fg=ACCENT2,
                      font=("Courier", 8), width=10, anchor="w")
        cl.pack(side="left", padx=4)
        dl = tk.Label(r0, text="", bg=bg, fg=GREEN,
                      font=("Courier", 8), width=10, anchor="w")
        dl.pack(side="left", padx=2)
        copy_btn = mk_btn(r0, t("arsenal_btn_copy", "➤ Copy"), lambda: None,
                          bg=ACCENT3, small=True)
        copy_btn.pack(side="right", padx=(2, 4))
        del_btn  = mk_btn(r0, "✕", lambda: None, bg=RED_C, small=True)
        del_btn.pack(side="right", padx=(0, 2))

        r1 = tk.Frame(row, bg=bg); r1.pack(fill="x")
        tk.Label(r1, text=t("label_level_add", "Level:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(6, 2))
        lv_sb = mk_int_spinbox(r1, tk.StringVar(), width=4,
                               font=("Courier", 8), from_=1, to=20)
        lv_sb.pack(side="left", padx=2)
        tk.Label(r1, text=t("label_mod_short", "Mod:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(8, 2))
        mod_sb = mk_int_spinbox(r1, tk.StringVar(), width=4,
                                font=("Courier", 8), from_=-99, to=99)
        mod_sb.pack(side="left", padx=2)
        tk.Label(r1, text=t("label_gear_colon", "Gear:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(8, 2))
        gear_chk = tk.Checkbutton(r1, variable=tk.BooleanVar(), bg=bg,
                                   selectcolor=CARD, activebackground=bg)
        gear_chk.pack(side="left")

        r2 = tk.Frame(row, bg=bg); r2.pack(fill="x")
        tk.Label(r2, text=t("label_desc", "Desc:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(6, 2))
        desc_entry = mk_entry(r2, tk.StringVar(), width=38, font=("Courier", 8))
        desc_entry.pack(side="left", padx=2, fill="x", expand=True)

        adf = tk.Frame(row, bg=bg)
        adf.pack_forget()

        tb = tk.Button(row, font=("Georgia", 7), bg=bg, fg=TEXT_DIM,
                       relief="flat", cursor="hand2", anchor="w",
                       activebackground=bg)
        tb.pack(fill="x", padx=6)

        return {
            "row": row, "r0": r0, "r1": r1, "r2": r2,
            "name_entry": name_entry, "up_btn": up_btn, "dn_btn": dn_btn,
            "cl": cl, "dl": dl,
            "copy_btn": copy_btn, "del_btn": del_btn,
            "lv_sb": lv_sb, "mod_sb": mod_sb, "gear_chk": gear_chk,
            "desc_entry": desc_entry, "adf": adf, "tb": tb,
            "bg": bg, "adf_open": False,
        }

    def _bind_arsenal_slot(self, slot, weap, i):
        """Rebind a pool slot to weapon dict at index i."""
        bg = CARD if i % 2 == 0 else PANEL

        # Recolour only on parity change
        if slot["bg"] != bg:
            slot["bg"] = bg
            for frame in (slot["row"], slot["r0"], slot["r1"],
                          slot["r2"], slot["adf"]):
                frame.configure(bg=bg)
            for child in slot["row"].winfo_children():
                try: child.configure(bg=bg)
                except Exception: pass
                for gc in child.winfo_children():
                    try: gc.configure(bg=bg)
                    except Exception: pass

        # Close adf panel if open (data differs after rebind)
        if slot["adf_open"]:
            slot["adf"].pack_forget()
            for w in slot["adf"].winfo_children():
                w.destroy()
            slot["adf_open"] = False

        # Ensure Tk vars exist on the weapon dict
        if "_tk_name" not in weap:
            weap["_tk_name"]  = tk.StringVar(value=str(weap.get("name",     "")))
            weap["_tk_level"] = tk.StringVar(value=str(weap.get("level",    "1")))
            weap["_tk_mod"]   = tk.StringVar(value=str(weap.get("modifier", "0")))
            weap["_tk_gear"]  = tk.BooleanVar(value=bool(weap.get("gear",   False)))
            weap["_tk_desc"]  = tk.StringVar(value=str(weap.get("desc",     "")))

        # Rebind widgets to Tk vars
        slot["name_entry"].configure(textvariable=weap["_tk_name"])
        slot["lv_sb"].configure(textvariable=weap["_tk_level"],
                                from_=0 if weap["_tk_gear"].get() else 1)
        slot["mod_sb"].configure(textvariable=weap["_tk_mod"])
        slot["gear_chk"].configure(variable=weap["_tk_gear"])
        slot["desc_entry"].configure(textvariable=weap["_tk_desc"])

        # Sync plain-dict fields from Tk vars on every write
        def _sync(w=weap):
            w["name"]     = w["_tk_name"].get()
            w["level"]    = w["_tk_level"].get()
            w["modifier"] = w["_tk_mod"].get()
            w["gear"]     = w["_tk_gear"].get()
            w["desc"]     = w["_tk_desc"].get()
            self._update_row(self._weapons.index(w))

        # Strip old traces before adding new ones
        for key in ("_tk_name", "_tk_level", "_tk_mod", "_tk_desc"):
            var = weap[key]
            for tid in list(var.trace_info()):
                try: var.trace_remove(tid[0], tid[1])
                except Exception: pass

        weap["_tk_name"].trace_add( "write", lambda *_, w=weap: _sync(w))
        weap["_tk_level"].trace_add("write", lambda *_, w=weap: _sync(w))
        weap["_tk_mod"].trace_add(  "write", lambda *_, w=weap: _sync(w))
        weap["_tk_desc"].trace_add( "write", lambda *_, w=weap: _sync(w))

        # Recompute cost/dmg labels
        lv   = int_or(weap["_tk_level"]); mod = int_or(weap["_tk_mod"])
        _dummy = {"advantages": weap.get("advantages", []),
                  "defects":    weap.get("defects",    []),
                  "gear":       weap["_tk_gear"].get()}
        cost = weapon_cost(_dummy, lv, mod, "Default")
        dmg  = weapon_damage(_dummy, lv)
        slot["cl"].configure(text=f"{cost} {t('label_cp', 'CP')}", bg=bg)
        slot["dl"].configure(text=f"{t('label_dmg_short', 'Dmg:')} {dmg}", bg=bg)
        self._cost_labels[i] = slot["cl"]
        self._dmg_labels[i]  = slot["dl"]

        # Gear checkbox — also updates level spinbox min
        def _on_gear(s=slot, w=weap, idx=i):
            s["lv_sb"].configure(from_=0 if w["_tk_gear"].get() else 1)
            self._update_row(idx)
        slot["gear_chk"].configure(command=_on_gear)

        # Copy / delete / up / down buttons
        slot["copy_btn"].configure(command=lambda idx=i: self._copy_to_char(idx))
        slot["del_btn"].configure( command=lambda idx=i: self._delete(idx))
        slot["up_btn"].configure(  command=lambda idx=i: self._move(idx, -1))
        slot["dn_btn"].configure(  command=lambda idx=i: self._move(idx, +1))

        # Adv/Def toggle button
        def _upd_tb(s=slot, w=weap):
            wa = weap_adv_weight(w.get("advantages", []))
            wd = weap_def_weight(w.get("defects",    []))
            parts = []
            if wa: parts.append(f"+{wa}")
            if wd: parts.append(f"-{wd}")
            weight_str = "  [" + ", ".join(parts) + "]" if parts else ""
            arrow = "▼" if s["adf_open"] else "▶"
            if s["adf_open"]:
                summary = weight_str
            else:
                adv_names = [display_name(e[0] if isinstance(e, (list, tuple)) else e)
                             for e in w.get("advantages", [])]
                def_names = [display_name(e[0] if isinstance(e, (list, tuple)) else e)
                             for e in w.get("defects", [])]
                all_names = adv_names + def_names
                names_str = "  " + ", ".join(all_names) if all_names else ""
                summary = names_str + weight_str
            s["tb"].config(text=f"{arrow} {t('label_adv_def', 'Adv/Def')}{summary}")

        def _adf_notify(idx=i, upd=_upd_tb):
            upd()
            self._update_row(idx)

        def _toggle(s=slot, w=weap, upd=_upd_tb, cb=_adf_notify):
            if s["adf_open"]:
                s["adf"].pack_forget()
                s["adf_open"] = False
            else:
                build_adv_def_panel(s["adf"], w, s["bg"], cb)
                s["adf"].pack(fill="x", padx=6, pady=(2, 0))
                s["adf_open"] = True
            upd()

        slot["tb"].configure(command=_toggle)
        _upd_tb()

    # ── Rebuild the weapon rows (pool-based) ──────────────────────────────────
    def _rebuild_list(self):
        # Strip traces from all weapons first
        for w in self._weapons:
            for key in ("_tk_name", "_tk_level", "_tk_mod", "_tk_desc"):
                var = w.get(key)
                if var is not None:
                    for tid in list(var.trace_info()):
                        try: var.trace_remove(tid[0], tid[1])
                        except Exception: pass

        n = len(self._weapons)
        self._cost_labels = {}
        self._dmg_labels  = {}

        # Grow pool if needed
        while len(self._pool) < n:
            self._pool.append(self._make_arsenal_slot(len(self._pool)))

        # Empty-state label
        if self._empty_lbl is None:
            self._empty_lbl = tk.Label(
                self._list_frame,
                text=t("arsenal_empty", "No weapons yet."),
                bg=BG, fg=TEXT_DIM, font=("Georgia", 9, "italic"))

        if n == 0:
            self._empty_lbl.pack(padx=12, pady=8)
        else:
            self._empty_lbl.pack_forget()
            for i, weap in enumerate(self._weapons):
                self._bind_arsenal_slot(self._pool[i], weap, i)
                self._pool[i]["row"].pack(fill="x", padx=4, pady=1)

        # Hide surplus pool slots
        for i in range(n, len(self._pool)):
            slot = self._pool[i]
            slot["row"].pack_forget()
            if slot["adf_open"]:
                slot["adf"].pack_forget()
                for w in slot["adf"].winfo_children():
                    w.destroy()
                slot["adf_open"] = False

        # "＋ New Weapon" button — always at the bottom
        # Re-pack it so it stays below the rows (pack order matters)
        if not hasattr(self, "_quick_add_btn"):
            self._quick_add_btn = mk_btn(
                self._list_frame,
                t('btn_add_weapon', '+ New Weapon'),
                self._quick_add, bg=ACCENT3)
        self._quick_add_btn.pack_forget()
        self._quick_add_btn.pack(pady=(6, 4))

    def _quick_add(self):
        n = f"{t('arsenal_weapon_default_name', 'Weapon')} {len(self._weapons) + 1}"
        self._weapons.append({
            "name": n, "level": "1", "modifier": "0",
            "gear": False, "desc": "", "advantages": [], "defects": [],
        })
        self._rebuild_list()
        self._set_status(t("arsenal_status_added", 'Added "{name}".').format(name=n))



    def _update_row(self, idx):
        if idx >= len(self._weapons): return
        weap = self._weapons[idx]
        try:
            lv  = int_or(weap.get("_tk_level", weap.get("level",  "1")))
            mod = int_or(weap.get("_tk_mod",   weap.get("modifier","0")))
        except (ValueError, TypeError):
            lv, mod = 1, 0
        gear = weap["_tk_gear"].get() if "_tk_gear" in weap else bool(weap.get("gear"))
        _dummy = {"advantages": weap.get("advantages", []),
                  "defects":    weap.get("defects",    []),
                  "gear":       gear}
        cost = weapon_cost(_dummy, lv, mod, "Default")
        dmg  = weapon_damage(_dummy, lv)
        cl = self._cost_labels.get(idx)
        dl = self._dmg_labels.get(idx)
        if cl and cl.winfo_exists(): cl.config(text=f"{cost} {t('label_cp', 'CP')}")
        if dl and dl.winfo_exists(): dl.config(text=f"{t('label_dmg_short', 'Dmg:')} {dmg}")

    # ── Copy weapon to active character ───────────────────────────────────
    def _copy_to_char(self, idx):
        weap = self._weapons[idx]
        tab  = self.app.active_tab()
        if tab is None:
            messagebox.showwarning(
                t("arsenal_no_char_title", "No Character"),
                t("arsenal_no_char_body", "No character tab is open.\nOpen or create a character first."),
                parent=self)
            return

        def _norm(lst):
            out = []
            for e in lst:
                if isinstance(e, str):    out.append((e, 1))
                elif isinstance(e, list): out.append(tuple(e))
                else:                     out.append(e)
            return out

        # Read current values from Tk vars if they exist, else from plain fields
        def _get(key, tk_key, default=""):
            var = weap.get(tk_key)
            if var is not None and hasattr(var, "get"): return var.get()
            return weap.get(key, default)

        tab.state.weapons.append({
            "name":       tk.StringVar(value=str(_get("name",     "_tk_name",  ""))),
            "level":      tk.StringVar(value=str(_get("level",    "_tk_level", "1"))),
            "modifier":   tk.StringVar(value=str(_get("modifier", "_tk_mod",   "0"))),
            "gear":       tk.BooleanVar(value=bool(
                              weap["_tk_gear"].get() if "_tk_gear" in weap
                              else weap.get("gear", False))),
            "desc":       tk.StringVar(value=str(_get("desc",     "_tk_desc",  ""))),
            "advantages": _norm(weap.get("advantages", [])),
            "defects":    _norm(weap.get("defects",    [])),
        })
        tab._pages[1]._weap_list.rebuild()
        tab._update_all()
        tab.state._on_var()
        name = _get("name", "_tk_name", "Weapon")
        char_name = tab.state.char_name.get() or "the character"
        self._set_status(
            t("arsenal_status_copied", '"{name}" copied to {char}.').format(
                name=name, char=char_name))

    # ── Delete ────────────────────────────────────────────────────────────
    def _delete(self, idx):
        weap = self._weapons[idx]
        name = (weap["_tk_name"].get() if "_tk_name" in weap else weap.get("name", "?"))
        if not messagebox.askyesno(
                t("arsenal_delete_title", "Delete Weapon"),
                t("arsenal_delete_body", 'Remove "{name}" from the Arsenal?').format(name=name),
                parent=self, icon="warning"):
            return
        self._weapons.pop(idx)
        self._rebuild_list()
        self._set_status(t("arsenal_status_removed", 'Removed "{name}".').format(name=name))

    def _move(self, idx, direction):
        new_idx = idx + direction
        if 0 <= new_idx < len(self._weapons):
            self._weapons.insert(new_idx, self._weapons.pop(idx))
            self._rebuild_list()

    # ── Save ──────────────────────────────────────────────────────────────
    def _save(self):
        path = filedialog.asksaveasfilename(
            parent=self, initialdir=_default_dir(ARSENAL_DIR),
            initialfile="arsenal.json",
            defaultextension=".json",
            filetypes=[("BESM Arsenal", "*.json"), ("All files", "*.*")],
            title=t("arsenal_save_title", "Save Arsenal"))
        if not path: return
        # Flush Tk-var values back to plain fields before serialising
        serialised = []
        for w in self._weapons:
            serialised.append({
                "name":       w["_tk_name"].get()  if "_tk_name"  in w else w.get("name",  ""),
                "level":      w["_tk_level"].get() if "_tk_level" in w else w.get("level", "1"),
                "modifier":   w["_tk_mod"].get()   if "_tk_mod"   in w else w.get("modifier","0"),
                "gear":       w["_tk_gear"].get()  if "_tk_gear"  in w else w.get("gear",  False),
                "desc":       w["_tk_desc"].get()  if "_tk_desc"  in w else w.get("desc",  ""),
                "advantages": list(w.get("advantages", [])),
                "defects":    list(w.get("defects",    [])),
            })
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"arsenal": serialised}, f, indent=2)
            self._set_status(
                t("arsenal_status_saved", "Saved {n} weapon(s).").format(n=len(serialised)))
        except Exception as e:
            messagebox.showerror(t("msg_error", "Error"), f"{t('msg_error','Error')}:\n{e}",
                                 parent=self)

    # ── Load ──────────────────────────────────────────────────────────────
    def _load(self):
        path = filedialog.askopenfilename(
            parent=self, initialdir=_default_dir(ARSENAL_DIR),
            filetypes=[("BESM Arsenal", "*.json"), ("All files", "*.*")],
            title=t("arsenal_load_title", "Load Arsenal"))
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror(t("msg_error", "Error"), f"{t('msg_error','Error')}:\n{e}",
                                 parent=self)
            return

        weapons = data.get("arsenal", data if isinstance(data, list) else [])
        if not isinstance(weapons, list):
            messagebox.showerror(t("msg_error", "Error"),
                                 t("arsenal_invalid_file", "Invalid arsenal file."),
                                 parent=self)
            return

        def _norm(lst):
            out = []
            for e in lst:
                if isinstance(e, str):    out.append((e, 1))
                elif isinstance(e, list): out.append(tuple(e))
                else:                     out.append(e)
            return out

        self._weapons = []
        for w in weapons:
            self._weapons.append({
                "name":       str(w.get("name",     "Unnamed")),
                "level":      str(w.get("level",    "1")),
                "modifier":   str(w.get("modifier", "0")),
                "gear":       bool(w.get("gear",    False)),
                "desc":       str(w.get("desc",     "")),
                "advantages": _norm(w.get("advantages", [])),
                "defects":    _norm(w.get("defects",    [])),
            })
        self._rebuild_list()
        self._set_status(
            t("arsenal_status_loaded", "Loaded {n} weapon(s).").format(n=len(self._weapons)))

    # ── Helpers ───────────────────────────────────────────────────────────
    def _set_status(self, msg):
        self._status_var.set(msg)
        self.after(4000, lambda: self._status_var.set("")
                   if self._status_var.get() == msg else None)

    def _on_close(self):
        self.withdraw()   # hide rather than destroy — preserves state


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN APPLICATION  — just the window, tab bar, and global style
# ─────────────────────────────────────────────────────────────────────────────

class BESMApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BESM 2nd Edition — Character Creator")
        self.configure(bg=BG)
        self.geometry("1260x760")
        self.minsize(1100, 640)

        self._apply_ttk_style()
        self._build_tab_bar()
        self._new_tab()          # open with one blank character
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<Control-z>", self._undo_active)
        self.bind_all("<Control-Z>", self._undo_active)

    def _on_close(self):
        unsaved = [t for t in self._tabs if t.state._unsaved]
        if unsaved:
            names = ", ".join(
                f"'{t.state.char_name.get() or 'Unnamed'}'"
                for t in unsaved)
            if not messagebox.askyesno(
                    "Unsaved changes",
                    f"{len(unsaved)} character(s) have unsaved changes:\n"
                    f"{names}\n\nQuit anyway?"):
                return
        self.destroy()

    # ── Style ─────────────────────────────────────────────────────────────
    def _apply_ttk_style(self):
        s = ttk.Style(self)
        try:   s.theme_use("clam")
        except Exception: pass
        s.configure("TCombobox", fieldbackground=ENTRY_BG, background=CARD,
                    foreground="black", selectbackground=ACCENT)
        s.configure("Vertical.TScrollbar", background=PANEL,
                    troughcolor=BG, arrowcolor=TEXT_DIM)
        s.map("Vertical.TScrollbar", background=[("active", BORDER)])

    # ── Tab bar ───────────────────────────────────────────────────────────
    def _build_tab_bar(self):
        self._tabs       = []   # list of CharacterTab
        self._active_idx = -1

        topbar = tk.Frame(self, bg=CARD, pady=0)
        topbar.pack(side="top", fill="x")

        # App title
        tk.Label(topbar, text="⚔  BESM 2E  ⚔", bg=CARD, fg=ACCENT,
                 font=("Georgia", 12, "bold"), padx=12
                 ).pack(side="left")

        # New-tab button
        self._new_tab_btn = mk_btn(topbar, t("btn_new_tab", "+ New Character"), self._new_tab,
               bg=NAV_INACT, small=True)
        self._new_tab_btn.pack(side="left", padx=4, pady=4)

        # Arsenal button
        self._arsenal_btn = mk_btn(topbar, "⚔ The Arsenal", self._open_arsenal,
               bg=ACCENT3, small=True)
        self._arsenal_btn.pack(side="left", padx=4, pady=4)

        # Language selector (right side of topbar)
        if len(_LANGS) > 1:
            lang_frame = tk.Frame(topbar, bg=CARD)
            lang_frame.pack(side="right", padx=8)
            tk.Label(lang_frame, text="🌐", bg=CARD, fg=TEXT_DIM,
                     font=("Georgia", 10)).pack(side="left")
            self._lang_var = tk.StringVar(value=_LANG)
            lang_labels = [label for _, label, _, _d in _LANGS]
            lang_combo = ttk.Combobox(lang_frame, textvariable=self._lang_var,
                                      values=lang_labels, state="readonly",
                                      width=10, font=("Georgia", 9))
            # Set current display label
            for code, label, _, _is_def in _LANGS:
                if code == _LANG:
                    self._lang_var.set(label)
            lang_combo.pack(side="left", padx=4, pady=4)
            lang_combo.bind("<<ComboboxSelected>>", self._on_lang_change)

        # Tab buttons container (scrollable row)
        self._tab_btn_frame = tk.Frame(topbar, bg=CARD)
        self._tab_btn_frame.pack(side="left", fill="x", expand=True, padx=4)

        # Character page area
        self._char_area = tk.Frame(self, bg=BG)
        self._char_area.pack(fill="both", expand=True)

    def active_tab(self):
        """Return the currently visible CharacterTab, or None."""
        if 0 <= self._active_idx < len(self._tabs):
            return self._tabs[self._active_idx]
        return None

    def _open_arsenal(self):
        if not hasattr(self, "_arsenal") or not self._arsenal.winfo_exists():
            self._arsenal = ArsenalWindow(self)
        else:
            self._arsenal.deiconify()
            self._arsenal.lift()

    def _new_tab(self, data=None):
        tab = CharacterTab(self._char_area, self)
        if data:
            tab.state.from_dict(data)
            tab._pages[1].rebuild_lists()
            tab._pages[2].rebuild_list()
            tab._pages[3].rebuild_all()
            tab._pages[4].rebuild_all_mechas()
            tab._update_all()
        self._tabs.append(tab)
        if hasattr(self, '_new_tab_btn'):
            self._new_tab_btn.config(text=t('btn_new_tab','+ New Character'))
        self._rebuild_tab_buttons()
        self._switch_to(len(self._tabs) - 1)

    def _rebuild_tab_buttons(self):
        """Rebuild the character tab bar (colours only).
        Button text is bound via textvariable so name edits update live
        without needing to recreate the buttons on every keystroke.
        """
        for w in self._tab_btn_frame.winfo_children():
            w.destroy()
        for i, tab in enumerate(self._tabs):
            frm = tk.Frame(self._tab_btn_frame, bg=CARD)
            frm.pack(side="left", padx=(0, 1))
            is_active = (i == self._active_idx)
            bg = NAV_ACT if is_active else NAV_INACT
            fg = "white"  if is_active else TEXT_DIM
            tk.Button(frm, textvariable=tab.tab_label_var,
                      font=("Georgia", 9, "bold"),
                      bg=bg, fg=fg, relief="flat", cursor="hand2",
                      activebackground=NAV_ACT, activeforeground="white",
                      padx=10, pady=5,
                      command=lambda i=i: self._switch_to(i)
                      ).pack(side="left")
            # Close button — only show if more than one tab open
            if len(self._tabs) > 1:
                tk.Button(frm, text="×", font=("Georgia", 9, "bold"),
                          bg=bg, fg=fg, relief="flat", cursor="hand2",
                          activebackground=RED_C, activeforeground="white",
                          padx=4, pady=5,
                          command=lambda i=i: self._close_tab(i)
                          ).pack(side="left")

    def _switch_to(self, idx):
        if self._active_idx == idx:
            return
        # Hide current
        if 0 <= self._active_idx < len(self._tabs):
            self._tabs[self._active_idx].place_forget()
        self._active_idx = idx
        tab = self._tabs[idx]
        tab.place(relx=0, rely=0, relwidth=1, relheight=1,
                  in_=self._char_area)
        self._rebuild_tab_buttons()

    def _close_tab(self, idx):
        if len(self._tabs) <= 1:
            return   # never close the last tab
        tab = self._tabs[idx]
        if tab.state._unsaved:
            name = tab.state.char_name.get() or "Unnamed"
            if not messagebox.askyesno(
                    "Unsaved changes",
                    f"'{name}' has unsaved changes.\nClose without saving?"):
                return
        tab.destroy()
        self._tabs.pop(idx)
        new_idx = min(idx, len(self._tabs) - 1)
        self._active_idx = -1   # force re-show
        self._switch_to(new_idx)

    def update_tab_label(self, tab):
        """Called by CharacterTab when char_name changes."""
        if tab in self._tabs:
            self._rebuild_tab_buttons()

    def _undo_active(self, event=None):
        if 0 <= self._active_idx < len(self._tabs):
            active_tab = self._tabs[self._active_idx]
            active_tab.undo(event)

    def _on_lang_change(self, _event=None):
        selected_label = self._lang_var.get()
        for code, label, _, _is_def in _LANGS:
            if label == selected_label:
                self.switch_language(code)
                break

    def switch_language(self, lang_code):
        """Reload game data + UI strings for lang_code, then rebuild all tabs."""
        if lang_code == _LANG:
            return
        try:
            _apply_lang(lang_code)
        except ValueError as exc:
            messagebox.showerror(
                "Invalid formula in config",
                f"The TOML configuration for '{lang_code}' contains an unsafe formula:\n\n"
                f"{exc}\n\nOnly arithmetic expressions are allowed.\n"
                "Language was not switched."
            )
            return
        for tab in self._tabs:
            state = tab.state
            data  = state.to_dict()
            page  = tab._current_page
            # Suppress notifications BEFORE destroying widgets, so that
            # tkinter destroy events don't fire traces into dead label widgets.
            old_notify = state._notify
            state._notify = lambda *a, **k: None
            try:
                tab._container.destroy()
                tab._build_pages()
                state.from_dict(data)
                tab._pages[1].rebuild_lists()
                tab._pages[2].rebuild_list()
                tab._pages[3].rebuild_all()
                tab._pages[4].rebuild_all_mechas()
            finally:
                state._notify = old_notify
            tab._update_all()
            tab._show_page(page)
            # Update IO + nav button labels
            tab._rebuild_nav_labels()
        self._rebuild_tab_buttons()
        # Refresh Arsenal window labels if it is open
        if hasattr(self, "_arsenal") and self._arsenal.winfo_exists():
            self._arsenal._refresh_title()

class LevelledList(tk.Frame):
    def __init__(self, parent, state, title, items_source, name_list,
                 cost_label="CP", accent_color=ACCENT2, linear=False, title_color=ACCENT,
                 notify_override=None):
        super().__init__(parent, bg=BG)
        self.state        = state
        self.items_source = items_source
        self.name_list    = name_list
        self.cost_label   = cost_label
        self.accent_color = accent_color
        self.linear       = linear  # if True, always use Default (linear) formula
        self.title_color  = title_color
        self._inner       = None
        self._cost_labels = {}
        self._row_pool    = []   # list of pre-built row slot dicts (pool)
        # If a notify_override is supplied, use it instead of state._notify()
        self._notify = notify_override if notify_override is not None else state._notify
        # Pre-built name → costs lookup (avoids rebuilding dict on every event)
        self._name_dict   = {n: c for n, c in name_list}
        self._build(title)

    # ── Build add-panel + scrollable list ─────────────────────────────────
    def _build(self, title):
        if title:
            tk.Label(self, text=title, bg=BG, fg=self.title_color,
                     font=("Georgia", 12, "bold")).pack(anchor="w", padx=4)

        add = tk.Frame(self, bg=PANEL, pady=6)
        add.pack(fill="x", pady=(0, 0))

        self._new_name     = tk.StringVar(value=self.name_list[0][0])
        # Build display→key and key→display maps for translated combobox
        self._disp_to_key  = {display_name(n): n for n, _ in self.name_list if n is not None}
        self._key_to_disp  = {n: display_name(n) for n, _ in self.name_list if n is not None}
        self._new_name_disp = tk.StringVar(value=display_name(self.name_list[0][0]))
        first_costs        = self.name_list[0][1]
        self._new_cost_var = tk.StringVar(
            value=str(first_costs[0] if isinstance(first_costs, list) else first_costs))
        self._new_lv       = tk.StringVar(value="1")
        self._new_mod      = tk.StringVar(value="0")
        self._new_desc     = tk.StringVar(value="")

        # Row 0: Name combobox (shows translated names, stores English key internally)
        tk.Label(add, text=t("label_name_add","Name:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=0, column=0, padx=6)
        _disp_values = [display_name(n) for n, _ in self.name_list]
        name_cb = ttk.Combobox(add, textvariable=self._new_name_disp,
                     values=_disp_values,
                     width=24, state="readonly", font=("Georgia", 9))
        name_cb.grid(row=0, column=1, padx=4)

        # Row 1: Cost selector (shown only when multiple costs exist) + Level + Modifier
        self._cost_lbl  = tk.Label(add, text=t("label_cost_lv","Cost/Lv:"), bg=PANEL, fg=ACCENT2,
                                    font=("Georgia", 9))
        self._cost_cb   = ttk.Combobox(add, textvariable=self._new_cost_var,
                                        width=4, state="readonly",
                                        font=("Georgia", 9))

        tk.Label(add, text=t("label_level_add","Level:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=1, column=0, padx=6)
        mk_int_spinbox(add, self._new_lv, width=4, font=("Courier", 10), from_=1, to=20
                 ).grid(row=1, column=1, padx=4, sticky="w")
        tk.Label(add, text=t("label_modifier_add","Modifier:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=1, column=2, padx=4)
        mk_int_spinbox(add, self._new_mod, width=4, font=("Courier", 10), from_=-99, to=99
                 ).grid(row=1, column=3, padx=4)

        # Row 2: Desc
        tk.Label(add, text=t("label_desc","Desc:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=2, column=0, padx=6, pady=4)
        mk_entry(add, self._new_desc, width=36
                 ).grid(row=2, column=1, columnspan=5, sticky="ew", padx=4)
        mk_btn(add, "+ Add", self._add
               ).grid(row=3, column=0, columnspan=6, pady=6)

        # Keep a reference to the add frame for cost-selector placement
        self._add_frame = add

        def _on_name_change(*_):
            disp  = self._new_name_disp.get()
            name  = self._disp_to_key.get(disp, disp)
            self._new_name.set(name)   # keep English key in sync
            # Sentinel / separator — costs is None for separator entries
            if self._name_dict.get(name) is None and name in self._name_dict:
                first = next((n for n, c in self.name_list if c is not None), "")
                self._new_name.set(first)
                self._new_name_disp.set(display_name(first))
                return
            costs = self._name_dict.get(name, [1])
            if costs is None: costs = [1]
            if not isinstance(costs, list): costs = [costs]
            if len(costs) > 1:
                self._cost_lbl.grid(row=0, column=2, padx=4)
                self._cost_cb.config(values=[str(c) for c in costs])
                self._new_cost_var.set(str(costs[0]))
                self._cost_cb.grid(row=0, column=3, padx=4)
            else:
                self._cost_lbl.grid_remove()
                self._cost_cb.grid_remove()
                self._new_cost_var.set(str(costs[0]))

        name_cb.bind("<<ComboboxSelected>>", _on_name_change)
        self._new_name_disp.trace_add("write", _on_name_change)
        _on_name_change()   # set initial state

        list_outer = tk.Frame(self, bg=PANEL)
        list_outer.pack(fill="both", expand=True, pady=4)
        tk.Label(list_outer, text=t("label_added","Added"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9, "italic")).pack(anchor="w", padx=6, pady=2)
        sc_outer, self._inner = scrollable(list_outer, bg=PANEL)
        sc_outer.pack(fill="both", expand=True)

    def _add(self):
        name   = self._new_name.get()
        if self._name_dict.get(name) is None and name in self._name_dict: return  # separator
        costs  = self._name_dict.get(name, [1])
        if costs is None: costs = [1]
        if isinstance(costs, list):
            base = int(self._new_cost_var.get()) if len(costs) > 1 else costs[0]
        else:
            base = costs
        self.items_source.append({
            "name":      name,
            "base_cost": base,
            "level":     tk.StringVar(value=self._new_lv.get()),
            "desc":      tk.StringVar(value=self._new_desc.get()),
            "modifier":  tk.StringVar(value=self._new_mod.get()),
        })
        self._new_desc.set("")
        self._new_lv.set("1")
        self._new_mod.set("0")
        self.rebuild()
        # Adding an attribute/defect is a content change
        self.state._on_var()

    # ── Row pool ──────────────────────────────────────────────────────────
    # Each slot is a dict of the pre-built widgets for that row position.
    # On rebuild we rebind existing slots, create new ones, hide extras.
    # This avoids destroying and recreating widgets on every add/delete/reorder.

    def _strip_traces(self, item):
        """Remove all write-traces from an item's Tk vars."""
        for vk in ("level", "modifier", "desc"):
            if vk in item:
                var = item[vk]
                for tid in list(var.trace_info()):
                    try: var.trace_remove(tid[0], tid[1])
                    except Exception: pass

    def _make_row_slot(self, idx):
        """Create a new pooled row frame with all sub-widgets.
        All configurable parts are stored in the slot dict."""
        bg   = CARD if idx % 2 == 0 else PANEL
        row  = tk.Frame(self._inner, bg=bg, pady=3)

        r0   = tk.Frame(row, bg=bg); r0.pack(fill="x")
        name_lbl = tk.Label(r0, text="", bg=bg, fg=TEXT,
                            font=("Georgia", 9, "bold"), width=22, anchor="w")
        name_lbl.pack(side="left", padx=6)
        up_btn = mk_btn(r0, "▲", lambda: None, bg=CARD, small=True)
        up_btn.pack(side="left", padx=1)
        dn_btn = mk_btn(r0, "▼", lambda: None, bg=CARD, small=True)
        dn_btn.pack(side="left", padx=(1, 4))
        tk.Label(r0, text=t("label_lv_short", "Lv:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(4, 2))
        lv_sb = mk_int_spinbox(r0, tk.StringVar(), width=4,
                               font=("Courier", 8), from_=1, to=20)
        lv_sb.pack(side="left", padx=2)
        tk.Label(r0, text=t("label_mod_short", "Mod:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(6, 2))
        mod_sb = mk_int_spinbox(r0, tk.StringVar(), width=4,
                                font=("Courier", 8), from_=-99, to=99)
        mod_sb.pack(side="left", padx=2)
        cost_lbl = tk.Label(r0, text="", bg=bg, fg=self.accent_color,
                            font=("Courier", 8), width=14, anchor="w")
        cost_lbl.pack(side="left", padx=8)
        del_btn = mk_btn(r0, "✕", lambda: None, bg=RED_C, small=True)
        del_btn.pack(side="right", padx=6)

        # Cost/level row — one label OR one combobox; we keep both and show one
        cost_row = tk.Frame(row, bg=bg)
        cl_lbl   = tk.Label(cost_row, text="", bg=bg, fg=TEXT_DIM,
                            font=("Georgia", 8))
        cl_lbl.pack(side="left")
        cl_cb_var = tk.StringVar()
        cl_cb    = ttk.Combobox(cost_row, textvariable=cl_cb_var,
                                values=[], width=3, state="readonly",
                                font=("Georgia", 8))
        cl_cb.pack(side="left", padx=4)
        cl_cb.pack_forget()   # hidden until needed

        r2      = tk.Frame(row, bg=bg); r2.pack(fill="x")
        tk.Label(r2, text=t("label_desc", "Desc:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(6, 2))
        desc_entry = mk_entry(r2, tk.StringVar(), width=36, font=("Courier", 8))
        desc_entry.pack(side="left", padx=2, fill="x", expand=True)

        return {
            "row": row, "r0": r0, "cost_row": cost_row,
            "name_lbl": name_lbl, "up_btn": up_btn, "dn_btn": dn_btn,
            "lv_sb": lv_sb, "mod_sb": mod_sb,
            "cost_lbl": cost_lbl, "del_btn": del_btn,
            "cl_lbl": cl_lbl, "cl_cb": cl_cb, "cl_cb_var": cl_cb_var,
            "desc_entry": desc_entry,
            "bg": bg,   # remembered so rebuild can skip recolour when parity unchanged
        }

    def rebuild(self):
        n = len(self.items_source)

        # Strip traces from every item before rebinding
        for item in self.items_source:
            self._strip_traces(item)

        # Grow pool if needed
        while len(self._row_pool) < n:
            self._row_pool.append(self._make_row_slot(len(self._row_pool)))

        self._cost_labels = {}

        for i, item in enumerate(self.items_source):
            slot = self._row_pool[i]
            bg   = CARD if i % 2 == 0 else PANEL

            # ── Recolour only if stripe parity changed (e.g. after a delete) ──
            if slot["bg"] != bg:
                slot["bg"] = bg
                for w in (slot["row"], slot["r0"], slot["cost_row"]):
                    w.configure(bg=bg)
                for child in slot["row"].winfo_children():
                    try: child.configure(bg=bg)
                    except Exception: pass
                    for grandchild in child.winfo_children():
                        try: grandchild.configure(bg=bg)
                        except Exception: pass

            # ── Rebind name / cost label ───────────────────────────────────
            slot["name_lbl"].configure(text=display_name(item["name"]),
                                       bg=bg, fg=TEXT)

            af   = "Default" if self.linear else self.state.attr_formula.get()
            lv   = int_or(item["level"])
            mod  = int_or(item["modifier"])
            cost = attr_cost(item["base_cost"], lv, af) + mod
            slot["cost_lbl"].configure(text=f"{cost} {self.cost_label}",
                                       bg=bg, fg=self.accent_color)
            self._cost_labels[i] = slot["cost_lbl"]

            # ── Rebind spinboxes ───────────────────────────────────────────
            slot["lv_sb"].configure(textvariable=item["level"])
            slot["mod_sb"].configure(textvariable=item["modifier"])

            # ── Rebind desc entry ──────────────────────────────────────────
            slot["desc_entry"].configure(textvariable=item["desc"])

            # ── Cost-per-level row ─────────────────────────────────────────
            costs = self._name_dict.get(item["name"], [item["base_cost"]])
            if not isinstance(costs, list): costs = [costs]
            if len(costs) > 1:
                slot["cl_lbl"].configure(
                    text=f"{t('label_cost_lv','Cost/Lv')} {self.cost_label}:")
                slot["cl_cb"].configure(values=[str(c) for c in costs])
                slot["cl_cb_var"].set(str(item["base_cost"]))
                slot["cl_cb"].pack(side="left", padx=4)
                # rebind combobox selection
                def _cost_changed(v=slot["cl_cb_var"], it=item, idx=i):
                    try:
                        it["base_cost"] = int(v.get())
                        self._update_cost(idx)
                    except ValueError: pass
                slot["cl_cb"].bind("<<ComboboxSelected>>",
                                   lambda e, f=_cost_changed: f())
                slot["cost_row"].pack(anchor="w", padx=8)
            else:
                slot["cost_row"].pack_forget()

            # ── Rebind buttons ─────────────────────────────────────────────
            def _del(idx=i):
                self.state.push_undo(self.items_source, idx,
                                     self.items_source[idx])
                self.items_source.pop(idx)
                self.rebuild()
                self.state._on_var()

            def _up(idx=i):
                if idx > 0:
                    self.items_source.insert(idx-1, self.items_source.pop(idx))
                    self.rebuild(); self.state._on_var()

            def _dn(idx=i):
                if idx < len(self.items_source)-1:
                    self.items_source.insert(idx+1, self.items_source.pop(idx))
                    self.rebuild(); self.state._on_var()

            slot["del_btn"].configure(command=_del)
            slot["up_btn"].configure(command=_up)
            slot["dn_btn"].configure(command=_dn)

            # ── Traces ────────────────────────────────────────────────────
            item["level"].trace_add(
                "write", lambda *_, idx=i: (self._update_cost(idx),
                                            self.state._on_var()))
            item["modifier"].trace_add(
                "write", lambda *_, idx=i: (self._update_cost(idx),
                                            self.state._on_var()))
            if "desc" in item:
                item["desc"].trace_add(
                    "write", lambda *_: self.state._on_var())

            # Make sure the row is visible and in position
            slot["row"].pack(fill="x", padx=4, pady=1)

        # Hide pool slots beyond the current item count
        for i in range(n, len(self._row_pool)):
            self._row_pool[i]["row"].pack_forget()

    def _update_cost(self, idx):
        if idx >= len(self.items_source): return
        item = self.items_source[idx]
        af   = "Default" if self.linear else self.state.attr_formula.get()
        cost = attr_cost(item["base_cost"], int_or(item["level"]), af) + int_or(item["modifier"])
        lbl  = self._cost_labels.get(idx)
        if lbl and lbl.winfo_exists():
            lbl.config(text=f"{cost} {self.cost_label}")
        self._notify()



def build_adv_def_panel(container, weap, bg, notify_cb):
    """Populate a weapon's Advantages/Defects checkbox panel inside a
    fixed-height scrollable area.  Shared by Page2, MechaEditor, WeaponList
    add-form, and ArsenalWindow.
    weap        — weapon dict with 'advantages' and 'defects' lists
    bg          — background colour of the containing row
    notify_cb   — callable to fire when a value changes
    """
    for w in container.winfo_children():
        w.destroy()

    # Use the shared scrollable() helper so the canvas is automatically
    # registered in _SCROLL_CANVASES and picked up by _scroll_handler.
    sc_outer, inner = scrollable(container, bg=bg)
    sc_outer.pack(fill="both", expand=True)
    # Clamp the canvas height so it doesn't expand to fill the whole window.
    canvas = [c for c in sc_outer.winfo_children()
              if isinstance(c, tk.Canvas)][0]
    canvas.configure(height=160, yscrollincrement=10)

    def _section(parent, items_data, stored_list, label_text, label_fg):
        hdr = tk.Frame(parent, bg=bg); hdr.pack(fill="x")
        tk.Label(hdr, text=label_text, bg=bg, fg=label_fg,
                 font=("Georgia", 8, "bold")).pack(anchor="w", padx=2)
        grid = tk.Frame(parent, bg=bg); grid.pack(fill="x")
        COLS = 3
        for idx, (iname, iweight, ilevelled) in enumerate(items_data):
            cur_lv = 0
            for e in stored_list:
                n = e[0] if isinstance(e, (list, tuple)) else e
                if n == iname:
                    cur_lv = e[1] if isinstance(e, (list, tuple)) and len(e) > 1 else 1
                    break
            max_lv = 3 if iname in ("Devastating", "Ineffective") else 20
            cell = tk.Frame(grid, bg=bg)
            cell.grid(row=idx // COLS, column=idx % COLS, sticky="w", padx=2, pady=1)
            chk_var = tk.BooleanVar(value=cur_lv > 0)
            lv_var  = tk.IntVar(value=min(max(cur_lv, 1), max_lv))

            def _toggle(cv=chk_var, lv=lv_var, n=iname, sl=stored_list, m=max_lv):
                sl[:] = [e for e in sl
                         if (e[0] if isinstance(e, (list, tuple)) else e) != n]
                if cv.get():
                    sl.append((n, min(lv.get(), m)))
                notify_cb()

            def _lv_change(lv=lv_var, cv=chk_var, n=iname, sl=stored_list, m=max_lv):
                if cv.get():
                    sl[:] = [e for e in sl
                             if (e[0] if isinstance(e, (list, tuple)) else e) != n]
                    sl.append((n, min(lv.get(), m)))
                    notify_cb()

            tk.Checkbutton(cell, text=display_name(iname), variable=chk_var, command=_toggle,
                           bg=bg, fg=label_fg, selectcolor=CARD,
                           activebackground=bg, font=("Georgia", 7)).pack(side="left")
            if ilevelled:
                sb2 = tk.Spinbox(cell, from_=1, to=max_lv, width=2,
                                 textvariable=lv_var, bg=ENTRY_BG, fg=TEXT,
                                 buttonbackground=CARD, relief="flat",
                                 font=("Courier", 7), command=_lv_change)
                sb2.pack(side="left", padx=(1, 0))
                sb2.bind("<FocusOut>", lambda e, f=_lv_change: f())

    al = tk.Frame(inner, bg=bg); al.pack(fill="x")
    _section(al, WEAPON_ADVANTAGES, weap["advantages"],
             t("label_advantages_colon", "Advantages:"), GREEN)
    dl = tk.Frame(inner, bg=bg); dl.pack(fill="x", pady=(4, 0))
    _section(dl, WEAPON_DEFECTS, weap["defects"],
             t("label_weapon_defects_colon", "Weapon Defects:"), ACCENT)


# ─────────────────────────────────────────────────────────────────────────────
#  SHARED: Weapon list widget
# ─────────────────────────────────────────────────────────────────────────────

class WeaponList(tk.Frame):
    """Self-contained weapon add-panel + scrollable list of weapon rows.

    Parameters
    ----------
    parent           : tk parent widget
    weapons          : the mutable list of weapon dicts
    attr_formula_cb  : callable() → str  — returns the current formula name
    notify_cb        : callable()        — fires whenever data changes
    cost_unit        : "CP" or "MP"
    state            : CharacterState    — for marking unsaved changes
    """
    def __init__(self, parent, weapons, attr_formula_cb, notify_cb,
                 cost_unit="CP", undo_cb=None, state=None):
        super().__init__(parent, bg=PANEL)
        self.weapons         = weapons
        self._formula        = attr_formula_cb
        self._notify         = notify_cb
        self._undo_cb        = undo_cb  # callable(list_ref, idx, item)
        self.state           = state    # CharacterState for marking unsaved
        self._cost_unit_src  = cost_unit  # str or callable → str
        self._cost_labels    = {}
        self._dmg_labels     = {}
        self._weap_inner     = None
        self._weap_pool      = []   # pool of reusable row slot dicts
        self._build_add_panel()
        self._build_list_area()

    @property
    def cost_unit(self):
        return self._cost_unit_src() if callable(self._cost_unit_src) else self._cost_unit_src

    # ── Add panel ─────────────────────────────────────────────────────────
    def _build_add_panel(self):
        add = tk.Frame(self, bg=PANEL, pady=6)
        add.pack(fill="x")

        self._nw_name  = tk.StringVar(value="")
        self._nw_level = tk.StringVar(value="1")
        self._nw_mod   = tk.StringVar(value="0")
        self._nw_gear  = tk.BooleanVar(value=False)
        self._nw_desc  = tk.StringVar(value="")
        # Staging dict for the Adv/Def toggle panel
        self._nw_staging = {"advantages": [], "defects": []}

        tk.Label(add, text=t("label_name_add","Name:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=0, column=0, padx=6)
        mk_entry(add, self._nw_name, width=18).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=4)
        tk.Label(add, text=t("label_level_add","Level:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=1, column=0, padx=6)
        _nw_lv_sb = mk_int_spinbox(add, self._nw_level, width=4, font=("Courier", 10), from_=1, to=20)
        _nw_lv_sb.grid(row=1, column=1, padx=4)
        tk.Label(add, text=t("label_modifier_add","Modifier:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=1, column=2, padx=4)
        mk_int_spinbox(add, self._nw_mod, width=4, font=("Courier", 10), from_=-99, to=99
                 ).grid(row=1, column=3, padx=4)
        tk.Label(add, text=t("label_gear_colon","Gear:"),     bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=1, column=4, padx=4)
        tk.Checkbutton(add, variable=self._nw_gear, bg=PANEL,
                       selectcolor=CARD, activebackground=PANEL,
                       command=lambda sb=_nw_lv_sb: sb.configure(
                           from_=0 if self._nw_gear.get() else 1)
                       ).grid(row=1, column=5, padx=2)
        tk.Label(add, text=t("label_desc","Desc:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=2, column=0, padx=6, pady=4)
        mk_entry(add, self._nw_desc, width=30).grid(
            row=2, column=1, columnspan=5, sticky="ew", padx=4)

        # ── Adv/Def toggle (same panel as weapon rows) ────────────────────
        adf_frame = tk.Frame(add, bg=PANEL)
        self._nw_adf_frame = adf_frame
        self._nw_adf_open  = False

        def _toggle_adf():
            if self._nw_adf_open:
                self._nw_adf_frame.grid_remove()
                self._nw_adf_open = False
            else:
                build_adv_def_panel(self._nw_adf_frame, self._nw_staging, PANEL, lambda: None)
                self._nw_adf_frame.grid()
                self._nw_adf_open = True
            _upd_adf_btn()

        def _upd_adf_btn():
            wa = weap_adv_weight(self._nw_staging.get("advantages", []))
            wd = weap_def_weight(self._nw_staging.get("defects",    []))
            parts = []
            if wa: parts.append(f"+{wa}")
            if wd: parts.append(f"-{wd}")
            weight_str = "  [" + ", ".join(parts) + "]" if parts else ""
            arrow = "▼" if self._nw_adf_open else "▶"
            if self._nw_adf_open:
                summary = weight_str
            else:
                adv_names = [display_name(e[0] if isinstance(e, (list, tuple)) else e)
                             for e in self._nw_staging.get("advantages", [])]
                def_names = [display_name(e[0] if isinstance(e, (list, tuple)) else e)
                             for e in self._nw_staging.get("defects", [])]
                all_names = adv_names + def_names
                names_str = "  " + ", ".join(all_names) if all_names else ""
                summary = names_str + weight_str
            self._nw_adf_btn.config(
                text=f"{arrow} {t('label_adv_def','Adv/Def')}{summary}")

        self._nw_adf_btn = tk.Button(
            add, font=("Georgia", 8), bg=PANEL, fg=TEXT_DIM,
            relief="flat", cursor="hand2", anchor="w",
            activebackground=PANEL, command=_toggle_adf)
        _upd_adf_btn()
        self._nw_adf_btn.grid(row=3, column=0, columnspan=6,
                               sticky="w", padx=4, pady=(4, 0))
        adf_frame.grid(row=4, column=0, columnspan=6, sticky="ew", padx=4, pady=2)
        adf_frame.grid_remove()

        mk_btn(add, t("btn_add_weapon","+ Add Weapon"), self._add).grid(
            row=5, column=0, columnspan=6, pady=6)

    def _build_list_area(self):
        lo = tk.Frame(self, bg=PANEL)
        lo.pack(fill="both", expand=True, pady=4)
        tk.Label(lo, text=t("label_added_weapons","Added Weapons"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9, "italic")).pack(anchor="w", padx=6, pady=2)
        sc_outer, self._weap_inner = scrollable(lo, bg=PANEL)
        sc_outer.pack(fill="both", expand=True)

    # ── Add ───────────────────────────────────────────────────────────────
    def _add(self):
        adv  = list(self._nw_staging.get("advantages", []))
        defs = list(self._nw_staging.get("defects",    []))
        n    = self._nw_name.get() or f"Weapon {len(self.weapons)+1}"
        weap = {
            "name":       tk.StringVar(value=n),
            "level":      tk.StringVar(value=self._nw_level.get()),
            "modifier":   tk.StringVar(value=self._nw_mod.get()),
            "gear":       tk.BooleanVar(value=self._nw_gear.get()),
            "desc":       tk.StringVar(value=self._nw_desc.get()),
            "advantages": adv, "defects": defs,
        }
        self.weapons.append(weap)
        self._nw_name.set(""); self._nw_level.set("1")
        self._nw_mod.set("0"); self._nw_gear.set(False); self._nw_desc.set("")
        # Reset staging and close the Adv/Def panel
        self._nw_staging["advantages"] = []
        self._nw_staging["defects"]    = []
        if self._nw_adf_open:
            self._nw_adf_frame.grid_remove()
            self._nw_adf_open = False
        self._nw_adf_btn.config(text=f"▶ {t('label_adv_def','Adv/Def')}")
        # Use pool rebuild — grows pool by exactly one slot, no widget destruction
        self.rebuild()
        # Adding a weapon is a content change
        if self.state and hasattr(self.state, '_on_var'):
            self.state._on_var()
        else:
            self._notify()

    # ── Weapon row pool ───────────────────────────────────────────────────
    def _make_weap_slot(self, idx):
        """Create one reusable weapon row frame with all sub-widgets."""
        bg  = CARD if idx % 2 == 0 else PANEL
        row = tk.Frame(self._weap_inner, bg=bg, pady=4)

        r0 = tk.Frame(row, bg=bg); r0.pack(fill="x")
        name_entry = mk_entry(r0, tk.StringVar(), width=18, font=("Georgia", 9))
        name_entry.pack(side="left", padx=(6, 2))
        up_btn = mk_btn(r0, "▲", lambda: None, bg=CARD, small=True)
        up_btn.pack(side="left", padx=1)
        dn_btn = mk_btn(r0, "▼", lambda: None, bg=CARD, small=True)
        dn_btn.pack(side="left", padx=(1, 4))
        cl = tk.Label(r0, text="", bg=bg, fg=ACCENT2,
                      font=("Courier", 8), width=12, anchor="w")
        cl.pack(side="left", padx=4)
        dl = tk.Label(r0, text="", bg=bg, fg=GREEN,
                      font=("Courier", 8), width=10, anchor="w")
        dl.pack(side="left", padx=4)
        del_btn = mk_btn(r0, "✕", lambda: None, bg=RED_C, small=True)
        del_btn.pack(side="right", padx=6)

        r1 = tk.Frame(row, bg=bg); r1.pack(fill="x")
        tk.Label(r1, text=t("label_level_add","Level:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(6, 2))
        lv_sb = mk_int_spinbox(r1, tk.StringVar(), width=4,
                               font=("Courier", 8), from_=1, to=20)
        lv_sb.pack(side="left", padx=2)
        tk.Label(r1, text=t("label_mod_short","Mod:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(8, 2))
        mod_sb = mk_int_spinbox(r1, tk.StringVar(), width=4,
                                font=("Courier", 8), from_=-99, to=99)
        mod_sb.pack(side="left", padx=2)
        tk.Label(r1, text=t("label_gear_colon","Gear:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(8, 2))
        gear_chk = tk.Checkbutton(r1, variable=tk.BooleanVar(), bg=bg,
                                   selectcolor=CARD, activebackground=bg)
        gear_chk.pack(side="left")

        r2 = tk.Frame(row, bg=bg); r2.pack(fill="x")
        tk.Label(r2, text=t("label_desc","Desc:"), bg=bg, fg=TEXT_DIM,
                 font=("Georgia", 8)).pack(side="left", padx=(6, 2))
        desc_entry = mk_entry(r2, tk.StringVar(), width=36, font=("Courier", 8))
        desc_entry.pack(side="left", padx=2, fill="x", expand=True)

        adf = tk.Frame(row, bg=bg)
        adf.pack_forget()

        tb = tk.Button(row, font=("Georgia", 7), bg=bg, fg=TEXT_DIM,
                       relief="flat", cursor="hand2", anchor="w",
                       activebackground=bg)
        tb.pack(fill="x", padx=6)

        return {
            "row": row, "r0": r0, "r1": r1, "r2": r2,
            "name_entry": name_entry, "up_btn": up_btn, "dn_btn": dn_btn,
            "cl": cl, "dl": dl, "del_btn": del_btn,
            "lv_sb": lv_sb, "mod_sb": mod_sb, "gear_chk": gear_chk,
            "desc_entry": desc_entry, "adf": adf, "tb": tb,
            "bg": bg, "adf_open": False,
        }

    def _bind_weap_slot(self, slot, weap, i):
        """Rebind a pool slot to a (possibly different) weapon dict."""
        bg = CARD if i % 2 == 0 else PANEL

        # Recolour only when stripe parity changed
        if slot["bg"] != bg:
            slot["bg"] = bg
            for frame in (slot["row"], slot["r0"], slot["r1"],
                          slot["r2"], slot["adf"]):
                frame.configure(bg=bg)
            for child in slot["row"].winfo_children():
                try: child.configure(bg=bg)
                except Exception: pass
                for gc in child.winfo_children():
                    try: gc.configure(bg=bg)
                    except Exception: pass

        # If Adv/Def panel was open, close and clear it (data will differ)
        if slot["adf_open"]:
            slot["adf"].pack_forget()
            for w in slot["adf"].winfo_children():
                w.destroy()
            slot["adf_open"] = False

        # Rebind Tk vars on widgets
        slot["name_entry"].configure(textvariable=weap["name"])
        slot["lv_sb"].configure(textvariable=weap["level"])
        slot["mod_sb"].configure(textvariable=weap["modifier"])
        slot["gear_chk"].configure(variable=weap["gear"])
        slot["desc_entry"].configure(textvariable=weap["desc"])

        # Recompute cost/dmg labels
        af   = self._formula()
        lv   = int_or(weap["level"]); mod = int_or(weap["modifier"])
        cost = weapon_cost(weap, lv, mod, af)
        dmg  = weapon_damage(weap, lv)
        slot["cl"].configure(text=f"{cost} {self.cost_unit}", bg=bg)
        slot["dl"].configure(text=f"{t('label_dmg_short','Dmg:')} {dmg}", bg=bg)
        self._cost_labels[i] = slot["cl"]
        self._dmg_labels[i]  = slot["dl"]

        # Rebind gear checkbox command — also updates level spinbox minimum
        def _on_gear(s=slot, w=weap, idx=i):
            is_gear = w["gear"].get()
            s["lv_sb"].configure(from_=0 if is_gear else 1)
            self._update_row(idx)

        slot["gear_chk"].configure(command=_on_gear)
        # Set spinbox min immediately to match current gear state
        slot["lv_sb"].configure(from_=0 if weap["gear"].get() else 1)

        # Rebind buttons
        def _del(idx=i):
            if self._undo_cb:
                self._undo_cb(self.weapons, idx, self.weapons[idx])
            self.weapons.pop(idx); self.rebuild()
            if self.state and hasattr(self.state, "_on_var"):
                self.state._on_var()
            else:
                self._notify()

        def _up(idx=i):
            if idx > 0:
                self.weapons.insert(idx-1, self.weapons.pop(idx))
                self.rebuild()
                if self.state and hasattr(self.state, "_on_var"):
                    self.state._on_var()
                else:
                    self._notify()

        def _dn(idx=i):
            if idx < len(self.weapons) - 1:
                self.weapons.insert(idx+1, self.weapons.pop(idx))
                self.rebuild()
                if self.state and hasattr(self.state, "_on_var"):
                    self.state._on_var()
                else:
                    self._notify()

        slot["del_btn"].configure(command=_del)
        slot["up_btn"].configure(command=_up)
        slot["dn_btn"].configure(command=_dn)

        # Adv/Def toggle button
        def _upd(s=slot, w=weap):
            wa = weap_adv_weight(w["advantages"])
            wd = weap_def_weight(w["defects"])
            parts = []
            if wa: parts.append(f"+{wa}")
            if wd: parts.append(f"-{wd}")
            weight_str = "  [" + ", ".join(parts) + "]" if parts else ""
            arrow = "▼" if s["adf_open"] else "▶"
            if s["adf_open"]:
                summary = weight_str
            else:
                adv_names = [display_name(e[0] if isinstance(e, (list, tuple)) else e)
                             for e in w["advantages"]]
                def_names = [display_name(e[0] if isinstance(e, (list, tuple)) else e)
                             for e in w["defects"]]
                all_names = adv_names + def_names
                names_str = "  " + ", ".join(all_names) if all_names else ""
                summary = names_str + weight_str
            s["tb"].config(text=f"{arrow} {t('label_adv_def','Adv/Def')}{summary}")

        def _adv_def_notify(idx=i, upd=_upd):
            upd()
            self._update_row(idx)
            if self.state and hasattr(self.state, "_on_var"):
                self.state._on_var()
            else:
                self._notify()

        def _toggle(s=slot, w=weap, upd=_upd, cb=_adv_def_notify):
            if s["adf_open"]:
                s["adf"].pack_forget(); s["adf_open"] = False
            else:
                build_adv_def_panel(s["adf"], w, s["bg"], cb)
                s["adf"].pack(fill="x", padx=6, pady=(2, 0))
                s["adf_open"] = True
            upd()

        slot["tb"].configure(command=_toggle)
        _upd()

        # Traces (strip old ones first)
        for vk in ("level", "modifier", "name", "desc"):
            if vk in weap:
                var = weap[vk]
                for tid in list(var.trace_info()):
                    try: var.trace_remove(tid[0], tid[1])
                    except Exception: pass

        weap["level"].trace_add(
            "write", lambda *_, idx=i: (self._update_row(idx),
                self.state._on_var() if self.state and hasattr(self.state, "_on_var")
                else self._notify()))
        weap["modifier"].trace_add(
            "write", lambda *_, idx=i: (self._update_row(idx),
                self.state._on_var() if self.state and hasattr(self.state, "_on_var")
                else self._notify()))
        weap.get("name") and weap["name"].trace_add(
            "write", lambda *_: (self.state._on_var()
                if self.state and hasattr(self.state, "_on_var") else self._notify()))
        weap.get("desc") and weap["desc"].trace_add(
            "write", lambda *_: (self.state._on_var()
                if self.state and hasattr(self.state, "_on_var") else self._notify()))

    # ── Rebuild (pool-based — reuses row widgets) ─────────────────────────
    def rebuild(self):
        n = len(self.weapons)
        self._cost_labels = {}
        self._dmg_labels  = {}

        # Grow pool if needed
        while len(self._weap_pool) < n:
            self._weap_pool.append(self._make_weap_slot(len(self._weap_pool)))

        for i, weap in enumerate(self.weapons):
            self._bind_weap_slot(self._weap_pool[i], weap, i)
            self._weap_pool[i]["row"].pack(fill="x", padx=4, pady=1)

        # Hide surplus pool slots
        for i in range(n, len(self._weap_pool)):
            slot = self._weap_pool[i]
            slot["row"].pack_forget()
            if slot["adf_open"]:
                slot["adf"].pack_forget()
                for w in slot["adf"].winfo_children():
                    w.destroy()
                slot["adf_open"] = False

    def _update_row(self, idx):
        if idx >= len(self.weapons): return
        w    = self.weapons[idx]
        af   = self._formula()
        lv   = int_or(w["level"]); mod = int_or(w["modifier"])
        cost = weapon_cost(w, lv, mod, af)
        dmg  = weapon_damage(w, lv)
        cl = self._cost_labels.get(idx)
        dl = self._dmg_labels.get(idx)
        if cl and cl.winfo_exists():
            cl.config(text=f"{cost} {self.cost_unit}")
        if dl and dl.winfo_exists():
            dl.config(text=f"{t('label_dmg_short','Dmg:')} {dmg}")
        self._notify()

    def notify_formula_change(self):
        """Refresh all cost labels after attr_formula changes."""
        af = self._formula()
        for idx, w in enumerate(self.weapons):
            lv   = int_or(w["level"]); mod = int_or(w["modifier"])
            cost = weapon_cost(w, lv, mod, af)
            cl = self._cost_labels.get(idx)
            if cl and cl.winfo_exists():
                cl.config(text=f"{cost} {self.cost_unit}")

# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 1 — Core Setup
# ─────────────────────────────────────────────────────────────────────────────

class Page1(tk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent, bg=BG)
        self.state           = state
        self._stat_cost_lbls = {}
        self._total_stat_lbl = None
        self._derived_lbls   = {}
        self._text_traces    = []   # [(var, trace_id), ...] — removed on destroy
        self._build()

    def destroy(self):
        """Remove StringVar traces before the Text widgets are torn down."""
        for var, tid in self._text_traces:
            try:
                var.trace_remove("write", tid)
            except Exception:
                pass
        self._text_traces.clear()
        super().destroy()

    def _build(self):
        outer, inner = scrollable(self, bg=BG)
        outer.pack(fill="both", expand=True)
        s = self.state

        nf = tk.Frame(inner, bg=PANEL, pady=6)
        nf.pack(fill="x", padx=14, pady=(14, 4))
        tk.Label(nf, text=t("label_name_colon","Character Name:"), bg=PANEL, fg=TEXT,
                 font=("Georgia", 10)).pack(side="left", padx=(8, 4))
        mk_entry(nf, s.char_name, width=32).pack(side="left")

        cpf = tk.Frame(inner, bg=PANEL, pady=6)
        cpf.pack(fill="x", padx=14, pady=4)
        tk.Label(cpf, text=t("label_cp_section","Character Points"), bg=PANEL, fg=ACCENT,
                 font=("Georgia", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=8, pady=(6, 4))
        cp_row = tk.Frame(cpf, bg=PANEL); cp_row.pack(fill="x", padx=8)
        tk.Label(cp_row, text=t("label_cp_total_colon","CP total:"), bg=PANEL, fg=TEXT,
                 font=("Georgia", 10)).pack(side="left", padx=(0, 4))
        mk_entry(cp_row, s.cp_total, width=6).pack(side="left")

        # ── Formula row: two panels side by side ──────────────────────
        formula_row = tk.Frame(inner, bg=BG)
        formula_row.pack(fill="x", padx=14, pady=4)

        ff = tk.Frame(formula_row, bg=PANEL, pady=6)
        ff.pack(side="left", fill="both", expand=True, padx=(0, 4))
        tk.Label(ff, text=t("label_stat_formula","Stat Cost Formula"), bg=PANEL, fg=ACCENT,
                 font=("Georgia", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=8, pady=(6, 4))
        rb_row = tk.Frame(ff, bg=PANEL); rb_row.pack(fill="x", padx=8, pady=(0,6))
        for name in FORMULA_NAMES:
            tk.Radiobutton(rb_row, text=display_name(name), variable=s.stat_formula, value=name,
                           bg=PANEL, fg=TEXT, selectcolor=CARD,
                           activebackground=PANEL, font=("Georgia", 10)
                           ).pack(side="left", padx=12)

        af = tk.Frame(formula_row, bg=PANEL, pady=6)
        af.pack(side="left", fill="both", expand=True, padx=(4, 0))
        tk.Label(af, text=t("label_attr_formula","Attribute Cost Formula"), bg=PANEL, fg=ACCENT,
                 font=("Georgia", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=8, pady=(6, 4))
        af_rb_row = tk.Frame(af, bg=PANEL); af_rb_row.pack(fill="x", padx=8, pady=(4,6))

        for name in ATTR_FORMULAS:
            tk.Radiobutton(af_rb_row, text=display_name(name), variable=s.attr_formula, value=name,
                           bg=PANEL, fg=TEXT, selectcolor=CARD,
                           activebackground=PANEL, font=("Georgia", 10)
                           ).pack(side="left", padx=12)

        sf_outer = tk.Frame(inner, bg=PANEL, pady=8)
        sf_outer.pack(fill="x", padx=14, pady=4)
        tk.Label(sf_outer, text=t("label_stats","Stats"), bg=PANEL, fg=ACCENT,
                 font=("Georgia", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=8, pady=(6, 4))
        sf = tk.Frame(sf_outer, bg=PANEL)
        sf.pack(fill="x", padx=8, pady=(0, 6))
        for col, hdr in enumerate([t("label_stat_col","Stat"), t("label_value_col","Value"), t("label_cp_cost_col","CP Cost")]):
            tk.Label(sf, text=hdr, bg=PANEL, fg=ACCENT2,
                     font=("Georgia", 9, "bold")
                     ).grid(row=0, column=col, padx=16, pady=4)
        for r, (eng_key, lbl, var) in enumerate(
                [("Body",  t("label_body","Body"),  s.body),
                 ("Mind",  t("label_mind","Mind"),  s.mind),
                 ("Soul",  t("label_soul","Soul"),  s.soul)], start=1):
            tk.Label(sf, text=lbl, bg=PANEL, fg=TEXT,
                     font=("Georgia", 10, "bold"), width=8
                     ).grid(row=r, column=0, padx=16)
            mk_int_spinbox(sf, var, width=5, from_=1, to=10).grid(row=r, column=1, padx=16, pady=4)
            cl = tk.Label(sf, text="0", bg=PANEL, fg=ACCENT2,
                          font=("Courier", 10), width=6)
            cl.grid(row=r, column=2, padx=16)
            self._stat_cost_lbls[eng_key] = cl
        tk.Label(sf, text=t("label_total_colon","Total:"), bg=PANEL, fg=TEXT_DIM,
                 font=("Georgia", 9)).grid(row=4, column=1, sticky="e")
        self._total_stat_lbl = tk.Label(sf, text="0", bg=PANEL, fg=ACCENT,
                                         font=("Georgia", 10, "bold"))
        self._total_stat_lbl.grid(row=4, column=2, padx=16, pady=4)

        mf_outer = tk.Frame(inner, bg=PANEL, pady=8)
        mf_outer.pack(fill="x", padx=14, pady=4)
        tk.Label(mf_outer, text=t("label_derived_mods","Derived Value Modifiers"), bg=PANEL, fg=ACCENT,
                 font=("Georgia", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=8, pady=(6, 4))
        mf = tk.Frame(mf_outer, bg=PANEL)
        mf.pack(fill="x", padx=8, pady=(0, 6))
        for col, (label, var) in enumerate([
                (t("label_hp_mod","Health Modifier"), s.hp_mod), (t("label_ep_mod","Energy Points Modifier"), s.ep_mod),
                (t("label_acv_mod","ACV Modifier"), s.acv_mod),   (t("label_dcv_mod","DCV Modifier"), s.dcv_mod),
                (t("label_sv_mod","Shock Value Modifier"), s.sv_mod)]):
            c = col * 2
            tk.Label(mf, text=label, bg=PANEL, fg=TEXT_DIM,
                     font=("Georgia", 9)
                     ).grid(row=0, column=c, sticky="e", padx=(12, 4))
            mk_int_spinbox(mf, var, width=5, from_=-99, to=99).grid(row=0, column=c+1,
                                             sticky="w", padx=(0, 12))

        df_outer = tk.Frame(inner, bg=PANEL, pady=8)
        df_outer.pack(fill="x", padx=14, pady=(4, 16))
        tk.Label(df_outer, text=t("label_derived","Derived Values"), bg=PANEL, fg=ACCENT,
                 font=("Georgia", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=8, pady=(6, 4))
        df = tk.Frame(df_outer, bg=PANEL)
        df.pack(fill="x", padx=8, pady=(0, 10))
        for col, key in enumerate(["HP", "EP", "ACV", "DCV", "SV"]):
            tk.Label(df, text=t(f"label_{key.lower()}", key), bg=PANEL, fg=TEXT_DIM,
                     font=("Georgia", 10)).grid(row=0, column=col*2, padx=14)
            lbl = tk.Label(df, text="—", bg=PANEL, fg=GREEN,
                           font=("Courier", 13, "bold"))
            lbl.grid(row=0, column=col*2+1, padx=6)
            self._derived_lbls[key] = lbl

        # ── Character Details + Equipment Notes ─────────────────────────
        notes_row = tk.Frame(inner, bg=BG)
        notes_row.pack(fill="both", expand=True, padx=14, pady=(4, 14))

        def _attach_autoresize(txt, min_lines=3, max_lines=15):
            def _resize(*_):
                # count lines in text (index returns 'line.column')
                linecount = int(txt.index('end-1c').split('.')[0])
                newh = max(min_lines, min(linecount, max_lines))
                txt.config(height=newh)
            txt.bind("<KeyRelease>", _resize)
            txt.bind("<FocusOut>", _resize)
            _resize()
            return _resize

        for label, var in [(t("label_details","Character Details"), s.char_details),
                            (t("label_equipment","Equipment & Adventuring Notes"), s.equip_notes)]:
            nf2 = tk.Frame(notes_row, bg=PANEL, pady=6)
            nf2.pack(side="top", fill="both", expand=True, padx=(0, 4), pady=(0, 4))
            tk.Label(nf2, text=label, bg=PANEL, fg=ACCENT,
                     font=("Georgia", 10, "bold"), anchor="w"
                     ).pack(fill="x", padx=8, pady=(4, 2))
            txt = tk.Text(nf2, height=4, width=32,
                          bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                          relief="flat", font=("Georgia", 9), wrap="word",
                          bd=1, highlightthickness=1, highlightbackground=BORDER)
            txt.pack(fill="x", expand=True, padx=8, pady=(0, 6))
            resize_fn = _attach_autoresize(txt)

            # Two-way sync: Text widget ↔ StringVar
            def _on_text(event, v=var, t=txt, fn=resize_fn):
                v.set(t.get("1.0", "end-1c"))
                fn()
            txt.bind("<KeyRelease>", _on_text)
            txt.bind("<FocusOut>",   _on_text)
            def _load_text(t=txt, v=var, fn=resize_fn):
                t.delete("1.0", "end")
                t.insert("1.0", v.get())
                fn()
            _load_text()
            # Store the trace ID so destroy() can remove it before the widget dies.
            _tid = var.trace_add("write", lambda *_, t=txt, v=var, fn=resize_fn: (
                t.delete("1.0", "end"), t.insert("1.0", v.get()), fn()
            ) if t.get("1.0", "end-1c") != v.get() else None)
            self._text_traces.append((var, _tid))

    def refresh(self):
        fn    = STAT_FORMULAS.get(self.state.stat_formula.get(), _formula_default)
        total = 0
        for lbl, var in [("Body", self.state.body),
                          ("Mind", self.state.mind),
                          ("Soul", self.state.soul)]:
            c = fn(int_or(var)); total += c
            if lbl in self._stat_cost_lbls:
                self._stat_cost_lbls[lbl].config(text=str(c))
        if self._total_stat_lbl:
            self._total_stat_lbl.config(text=str(total))
        d = self.state.derived()
        for key, lbl in self._derived_lbls.items():
            lbl.config(text=str(d[key]))


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 2 — Attributes & Weapons
# ─────────────────────────────────────────────────────────────────────────────

class Page2(tk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent, bg=BG)
        self.state       = state
        self._weap_inner = None
        self._weap_cost_labels = {}
        self._weap_dmg_labels  = {}
        self._build()

    def _build(self):
        left  = tk.Frame(self, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(8,4), pady=8)
        right = tk.Frame(self, bg=BG)
        right.pack(side="right", fill="both", expand=True, padx=(4,8), pady=8)

        self._attr_list = LevelledList(left, self.state, t("label_attributes","Attributes"),
                                       self.state.attributes, ATTRIBUTES,
                                       cost_label=t("label_cp","CP"), accent_color=ACCENT2)
        self._attr_list.pack(fill="both", expand=True)
        self._build_weapons(right)

    def rebuild_lists(self):
        self._attr_list.rebuild()
        if hasattr(self, '_weap_list'):
            self._weap_list.rebuild()
        self._rebuild_weap_rows()

    # ── Weapons ───────────────────────────────────────────────────────────
    def _build_weapons(self, parent):
        tk.Label(parent, text=t("label_weapons","Weapons"), bg=BG, fg=ACCENT,
                 font=("Georgia", 12, "bold")).pack(anchor="w", padx=4)
        self._weap_list = WeaponList(
            parent, self.state.weapons,
            attr_formula_cb=self.state.attr_formula.get,
            notify_cb=self.state._notify,
            cost_unit=lambda: t("label_cp","CP"),
            undo_cb=self.state.push_undo,
            state=self.state)
        self._weap_list.pack(fill="both", expand=True)

    def _rebuild_weap_rows(self):
        self._weap_list.rebuild()

    def _update_weap_row(self, idx):
        self._weap_list._update_row(idx)


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 3 — Defects
# ─────────────────────────────────────────────────────────────────────────────

class Page3(tk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent, bg=BG)
        self.state = state
        self._build()

    def _build(self):
        wrapper = tk.Frame(self, bg=BG)
        wrapper.pack(fill="both", expand=True, padx=8, pady=8)
        self._def_list = LevelledList(wrapper, self.state, t("label_defects","Defects"),
                                      self.state.defects, DEFECTS,
                                      cost_label=t("label_cp_refund","CP refund"),
                                      accent_color=ACCENT3, linear=True,
                                      title_color=ACCENT3)
        self._def_list.pack(fill="both", expand=True)

    def rebuild_list(self):
        self._def_list.rebuild()


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 4 — Skills
# ─────────────────────────────────────────────────────────────────────────────

class Page4(tk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent, bg=BG)
        self.state            = state
        self._skill_cost_lbl  = {}
        self._skill_total_lbl = {}
        self._cbt_cost_lbl    = {}
        self._cbt_total_lbl   = {}
        self._sp_lbl          = None
        self._build()

    def _build(self):
        s = self.state
        # Remove any stale skill_setting traces left by previous _build() calls.
        for _tid in getattr(self, '_setting_trace_ids', []):
            try: s.skill_setting.trace_remove("write", _tid)
            except Exception: pass
        self._setting_trace_ids = []

        top = tk.Frame(self, bg=PANEL, pady=6)
        top.pack(fill="x", padx=8, pady=(8,4))
        tk.Label(top, text=t("label_base_sp_colon","Base SP:"), bg=PANEL, fg=TEXT,
                 font=("Georgia", 10)).pack(side="left", padx=(8,4))
        mk_entry(top, s.sp_total, width=6).pack(side="left", padx=(0,16))
        tk.Label(top, text=t("label_setting", "Skill Setting") + ":", bg=PANEL, fg=TEXT,
                 font=("Georgia", 10)).pack(side="left", padx=(8,4))
        # Build translated display labels while keeping English keys as internal values.
        _setting_display = [display_name(s_) for s_ in SETTINGS]
        _setting_eng_map = {display_name(s_): s_ for s_ in SETTINGS}
        _setting_disp_var = tk.StringVar(value=display_name(s.skill_setting.get()))
        def _on_setting_change(*_):
            eng = _setting_eng_map.get(_setting_disp_var.get())
            if eng is not None:
                s.skill_setting.set(eng)
        _setting_disp_var.trace_add("write", _on_setting_change)
        _tid = s.skill_setting.trace_add("write", lambda *_: _setting_disp_var.set(
            display_name(s.skill_setting.get())))
        self._setting_trace_ids.append(_tid)
        ttk.Combobox(top, textvariable=_setting_disp_var, values=_setting_display,
                     width=18, state="readonly", font=("Georgia", 9)
                     ).pack(side="left")
        self._sp_lbl = tk.Label(top, text=f"{t('label_sp_display','SP:')} 0/0", bg=PANEL,
                                 fg=ACCENT2, font=("Courier", 10, "bold"))
        self._sp_lbl.pack(side="right", padx=12)

        cols = tk.Frame(self, bg=BG)
        cols.pack(fill="both", expand=True, padx=8, pady=4)
        left  = tk.Frame(cols, bg=BG); left.pack(side="left",  fill="both", expand=True, padx=(0,4))
        right = tk.Frame(cols, bg=BG); right.pack(side="right", fill="both", expand=True, padx=(4,0))

        self._build_col(left,  t("label_skills","Skills"),        SKILLS,
                        s.skill_levels, s.skill_descs, s.skill_mods,
                        self._skill_cost_lbl, self._skill_total_lbl, False)
        self._build_col(right, t("label_combat_skills","Combat Skills"), COMBAT_SKILLS,
                        s.combat_levels, s.combat_descs, s.combat_mods,
                        self._cbt_cost_lbl, self._cbt_total_lbl, True)

    def _build_col(self, parent, title, skill_dict, levels, descs, mods,
                   cost_map, total_map, is_combat):
        tk.Label(parent, text=title, bg=BG, fg=ACCENT,
                 font=("Georgia", 11, "bold")).pack(anchor="w", padx=4)
        outer, inner = scrollable(parent, bg=PANEL)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(inner, bg=CARD); hdr.pack(fill="x", padx=2, pady=(2,0))
        for col, (txt, w) in enumerate([(t("label_skill_col","Skill"),20),(t("label_lv_col","Lv"),3),(t("label_sp_lv_col","SP/Lv"),6),(t("label_mod_col","Mod"),4),(t("label_total_col","Total"),6),(t("label_description","Description"),14)]):
            tk.Label(hdr, text=txt, bg=CARD, fg=ACCENT2,
                     font=("Georgia", 9, "bold"), width=w, anchor="w"
                     ).grid(row=0, column=col, padx=4, pady=2)

        setting = self.state.skill_setting.get()
        for i, (name, data) in enumerate(sorted(skill_dict.items(), key=lambda kv: display_name(kv[0]).casefold())):
            bg  = CARD if i % 2 == 0 else PANEL
            row = tk.Frame(inner, bg=bg); row.pack(fill="x", padx=2)
            tag = (" ⚔" if data.get("is_attack") else " 🛡") if is_combat else ""
            tk.Label(row, text=display_name(name)+tag, bg=bg, fg=TEXT,
                     font=("Georgia", 9), width=20, anchor="w"
                     ).grid(row=0, column=0, padx=6, pady=2, sticky="w")
            lv_var = levels[name]
            tk.Spinbox(row, from_=0, to=100, width=3, textvariable=lv_var,
                       bg=ENTRY_BG, fg=TEXT, buttonbackground=CARD,
                       relief="flat", font=("Courier", 9)
                       ).grid(row=0, column=1, padx=2)
            c = data.get(setting, 0)
            clbl = tk.Label(row, text=str(c), bg=bg, fg=TEXT_DIM,
                            font=("Courier", 9), width=7)
            clbl.grid(row=0, column=2)
            mod_var = mods[name]
            tk.Spinbox(row, from_=-99, to=99, width=4, textvariable=mod_var,
                       bg=ENTRY_BG, fg=TEXT, buttonbackground=CARD,
                       relief="flat", font=("Courier", 9)
                       ).grid(row=0, column=3, padx=2)
            tlbl = tk.Label(row, text=str(int_or(lv_var) * c + int_or(mod_var)),
                            bg=bg, fg=ACCENT2, font=("Courier", 9), width=7)
            tlbl.grid(row=0, column=4)
            mk_entry(row, descs[name], width=14, font=("Courier", 8)
                     ).grid(row=0, column=5, padx=6, sticky="ew")
            cost_map[name]  = clbl
            total_map[name] = tlbl

    def refresh_all(self):
        setting = self.state.skill_setting.get()
        for name, clbl in self._skill_cost_lbl.items():
            c = SKILLS[name].get(setting, 0)
            lv = int_or(self.state.skill_levels[name])
            mod = int_or(self.state.skill_mods[name])
            clbl.config(text=str(c))
            self._skill_total_lbl[name].config(text=str(lv*c + mod))
        for name, clbl in self._cbt_cost_lbl.items():
            c = COMBAT_SKILLS[name].get(setting, 0)
            lv = int_or(self.state.combat_levels[name])
            mod = int_or(self.state.combat_mods[name])
            clbl.config(text=str(c))
            self._cbt_total_lbl[name].config(text=str(lv*c + mod))
        if self._sp_lbl:
            sp_s = self.state.sp_spent()
            sp_t = self.state.sp_total_effective()
            self._sp_lbl.config(text=f"{t('label_sp_display','SP:')} {sp_s}/{sp_t}",
                                 fg=GREEN if sp_s<=sp_t else RED_C)

    def rebuild_all(self):
        for w in self.winfo_children(): w.destroy()
        self._skill_cost_lbl.clear();  self._skill_total_lbl.clear()
        self._cbt_cost_lbl.clear();    self._cbt_total_lbl.clear()
        self._sp_lbl = None
        self._build()



# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 5 — Mecha
# ─────────────────────────────────────────────────────────────────────────────

class MechaEditor(tk.Frame):
    """
    Full editor for one MechaState.  Laid out like Page2+Page3:
    left half = Attributes & Weapons, right half = Defects.
    Uses MECHA_ALL_ATTRIBUTES and MECHA_ALL_DEFECTS combined lists.
    """
    def __init__(self, parent, mecha, char_state):
        super().__init__(parent, bg=BG)
        self.mecha      = mecha
        self.char_state = char_state
        self._weap_inner       = None
        self._weap_cost_labels = {}
        self._weap_dmg_labels  = {}
        self._text_traces      = []   # [(var, trace_id), ...] — removed on destroy
        self._build()

    def destroy(self):
        """Remove StringVar traces before Text widgets are torn down."""
        for var, tid in self._text_traces:
            try:
                var.trace_remove("write", tid)
            except Exception:
                pass
        self._text_traces.clear()
        super().destroy()

    def _build(self):
        # Top bar: mecha name + MP budget (outside scroll so always visible)
        top = tk.Frame(self, bg=PANEL, pady=4)
        top.pack(fill="x", padx=6, pady=(6,4))
        tk.Label(top, text=t("label_mecha_name","Mecha Name:"), bg=PANEL, fg=TEXT,
                 font=("Georgia", 10)).pack(side="left", padx=(8,4))
        mk_entry(top, self.mecha.name, width=24).pack(side="left")
        tk.Label(top, text=t("label_mp_total_colon","   MP total:"), bg=PANEL, fg=TEXT,
                 font=("Georgia", 10)).pack(side="left", padx=(16,4))
        mk_entry(top, self.mecha.mp_total, width=6).pack(side="left")
        self._mp_lbl = tk.Label(top, text=f"{t('label_mp_used','MP used:')} 0", bg=PANEL,
                                 fg=ACCENT2, font=("Courier", 10, "bold"))
        self._mp_lbl.pack(side="left", padx=12)
        self.mecha.mp_total.trace_add("write", lambda *_: self._refresh_mp())
        self._mhp_lbl = tk.Label(top, text=f"{t('label_hp_display','HP:')} 40", bg=PANEL,
                                 fg=ACCENT2, font=("Courier", 10, "bold"))
        self._mhp_lbl.pack(side="left", padx=12)
        self._refresh_mp()

        # Two-column layout inside a scrollable area
        sc_outer, inner = scrollable(self, bg=BG)
        sc_outer.pack(fill="both", expand=True, padx=6, pady=4)

        # Mecha details text area — inside scroll, above columns
        det_f = tk.Frame(inner, bg=PANEL, pady=4)
        det_f.pack(fill="both", expand=True, pady=(0,6))
        tk.Label(det_f, text=t("label_mecha_details","Mecha Details:"), bg=PANEL, fg=TEXT,
                 font=("Georgia", 10)).pack(side="left", padx=(8,4))
        det_txt = tk.Text(det_f, height=3, width=60,
                          bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                          relief="flat", font=("Georgia", 9), wrap="word",
                          bd=1, highlightthickness=1, highlightbackground=BORDER)
        det_txt.pack(fill="x", expand=True, padx=(0,8), pady=2)
        # autoresize same as other notes boxes
        def _attach_txt(txt, min_lines=2, max_lines=10):
            def _resize(*_):
                lines = int(txt.index('end-1c').split('.')[0])
                txt.config(height=max(min_lines, min(lines, max_lines)))
            txt.bind("<KeyRelease>", _resize)
            txt.bind("<FocusOut>", _resize)
            _resize()
            return _resize
        resize_fn_det = _attach_txt(det_txt)
        det_txt.insert("1.0", self.mecha.details.get())
        def _on_det(event, v=self.mecha.details, txt=det_txt):
            v.set(txt.get("1.0", "end-1c"))
            resize_fn_det()
        det_txt.bind("<KeyRelease>", _on_det)
        det_txt.bind("<FocusOut>",   _on_det)
        _det_tid = self.mecha.details.trace_add("write", lambda *_, t=det_txt, v=self.mecha.details: (
            t.delete("1.0", "end"), t.insert("1.0", v.get()), resize_fn_det()
        ) if t.get("1.0", "end-1c") != v.get() else None)
        self._text_traces.append((self.mecha.details, _det_tid))

        cols = tk.Frame(inner, bg=BG)
        cols.pack(fill="both", expand=True)

        left  = tk.Frame(cols, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,3))
        right = tk.Frame(cols, bg=BG)
        right.pack(side="right", fill="both", expand=True, padx=(3,0))

        # Notify wrapper: propagate to global state AND refresh MP label
        def _notify():
            self.char_state._notify()
            self._refresh_mp()

        # Left: Attributes only (full height)
        self._attr_list = LevelledList(left, self.char_state, t("label_attributes","Attributes"),
                                       self.mecha.attributes,
                                       MECHA_ALL_ATTRIBUTES,
                                       cost_label=t("label_mp","MP"), accent_color=ACCENT2,
                                       notify_override=_notify)
        self._attr_list.pack(fill="both", expand=True)

        # Right top: Weapons
        self._build_weapons(right, _notify)

        # Right bottom: Defects
        self._def_list = LevelledList(right, self.char_state, t("label_defects","Defects"),
                                      self.mecha.defects,
                                      MECHA_ALL_DEFECTS,
                                      cost_label=t("label_mp_refund","MP refund"),
                                      accent_color=ACCENT3, linear=True,
                                      title_color=ACCENT3,
                                      notify_override=_notify)
        self._def_list.pack(fill="both", expand=True, pady=(8,0))

    def _refresh_mp(self):
        af  = self.char_state.attr_formula.get()
        mp_s = self.mecha.mp_spent(af)
        mp_t = int_or(self.mecha.mp_total)
        self._mp_lbl.config(
            text=f"{t('label_mp_used','MP used:')} {mp_s}",
            fg=GREEN if mp_s<=mp_t else RED_C)
        mhp = mecha_hp(self.mecha)
        self._mhp_lbl.config(
            text=f"{t('label_hp_display','HP:')} {mhp}")


    # ── Weapons ──────────────────────────────────────────────────────────
    def _build_weapons(self, parent, notify_cb):
        tk.Label(parent, text=t("label_weapons","Weapons"), bg=BG, fg=ACCENT,
                 font=("Georgia", 12, "bold")).pack(anchor="w", padx=4)
        self._weap_list = WeaponList(
            parent, self.mecha.weapons,
            attr_formula_cb=self.char_state.attr_formula.get,
            notify_cb=notify_cb,
            cost_unit=lambda: t("label_mp","MP"),
            undo_cb=self.char_state.push_undo,
            state=self.char_state)
        self._weap_list.pack(fill="both", expand=True)

    def _rebuild_weap_rows(self):
        self._weap_list.rebuild()

    def _update_weap_row(self, idx):
        self._weap_list._update_row(idx)

    def rebuild(self):
        """Called when attr_formula changes or after data load."""
        self._attr_list.rebuild()
        self._def_list.rebuild()
        self._weap_list.rebuild()
        self._refresh_mp()


class Page5Mecha(tk.Frame):
    """
    Tab bar of mechas. Each character can own multiple mechas.
    """
    def __init__(self, parent, state):
        super().__init__(parent, bg=BG)
        self.state        = state
        self._active_idx  = -1
        self._editors     = []   # list of MechaEditor frames
        self._build_shell()

    def _build_shell(self):
        # Top bar: title + New Mecha button + mecha tabs
        top = tk.Frame(self, bg=CARD, pady=0)
        top.pack(side="top", fill="x")
        tk.Label(top, text=t("label_mecha_section","⚙  Mecha"), bg=CARD, fg=ACCENT,
                 font=("Georgia", 11, "bold"), padx=10).pack(side="left")
        mk_btn(top, t("btn_add_mecha","+ New Mecha"), self._new_mecha,
               bg=NAV_INACT, small=True).pack(side="left", padx=4, pady=4)
        self._tab_frame = tk.Frame(top, bg=CARD)
        self._tab_frame.pack(side="left", fill="x", expand=True)

        self._editor_area = tk.Frame(self, bg=BG)
        self._editor_area.pack(fill="both", expand=True)

        # Empty state label
        self._empty_lbl = tk.Label(
            self._editor_area,
            text="No mechas yet.  Click  + New Mecha  to add one.",
            bg=BG, fg=TEXT_DIM, font=("Georgia", 11, "italic"))
        self._empty_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def on_show(self):
        """Called when the page becomes visible."""
        self._rebuild_tabs()
        if self._editors and self._active_idx >= 0:
            self._editors[self._active_idx].rebuild()

    def rebuild_all_mechas(self):
        """Rebuild editor list from state (called after load)."""
        for ed in self._editors:
            ed.destroy()
        self._editors.clear()
        self._active_idx = -1
        for ms in self.state.mechas:
            ed = MechaEditor(self._editor_area, ms, self.state)
            self._editors.append(ed)
        self._rebuild_tabs()
        if self._editors:
            # Force _switch_to to run even though _active_idx starts at -1
            self._switch_to(0)
            # Rebuild lists/rows so weapons, attributes and defects are visible
            self._editors[0].rebuild()

    def rebuild_active(self):
        if 0 <= self._active_idx < len(self._editors):
            self._editors[self._active_idx].rebuild()

    def _new_mecha(self):
        ms = MechaState(notify_cb=self.state._notify, char_state=self.state)
        self.state.mechas.append(ms)
        ed = MechaEditor(self._editor_area, ms, self.state)
        self._editors.append(ed)
        self._rebuild_tabs()
        self._switch_to(len(self._editors) - 1)
        # Creating a new mecha is a change to the character
        self.state._on_var()

    def _rebuild_tabs(self):
        """Rebuild tab buttons (colours only — text comes from textvariable)."""
        for w in self._tab_frame.winfo_children():
            w.destroy()
        if not self._editors:
            self._empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
            return
        self._empty_lbl.place_forget()
        for i, ed in enumerate(self._editors):
            # Use the mecha's name StringVar directly as textvariable
            # so the button text updates live without any trace callbacks.
            is_active = (i == self._active_idx)
            bg = NAV_ACT if is_active else NAV_INACT
            fg = "white"  if is_active else TEXT_DIM
            frm = tk.Frame(self._tab_frame, bg=CARD); frm.pack(side="left", padx=(0,1))
            tk.Button(frm, textvariable=ed.mecha.name,
                      font=("Georgia", 9, "bold"),
                      bg=bg, fg=fg, relief="flat", cursor="hand2",
                      activebackground=NAV_ACT, activeforeground="white",
                      padx=10, pady=5,
                      command=lambda i=i: self._switch_to(i)).pack(side="left")
            tk.Button(frm, text="×", font=("Georgia", 9, "bold"),
                      bg=bg, fg=fg, relief="flat", cursor="hand2",
                      activebackground=RED_C, activeforeground="white",
                      padx=4, pady=5,
                      command=lambda i=i: self._close_mecha(i)).pack(side="left")
            # No trace_add here — textvariable handles live updates

    def _switch_to(self, idx):
        if self._active_idx == idx: return
        if 0 <= self._active_idx < len(self._editors):
            self._editors[self._active_idx].place_forget()
        self._active_idx = idx
        self._editors[idx].place(relx=0, rely=0, relwidth=1, relheight=1,
                                  in_=self._editor_area)
        self._editors[idx].rebuild()
        self._rebuild_tabs()

    def _close_mecha(self, idx):
        name = self.state.mechas[idx].name.get() or "this mecha"
        if not messagebox.askyesno("Delete Mecha",
                                   f"Delete \"{name}\"?\nThis cannot be undone.",
                                   icon="warning"):
            return
        self._editors[idx].destroy()
        self._editors.pop(idx)
        self.state.mechas.pop(idx)
        self._active_idx = -1
        if self._editors:
            self._switch_to(min(idx, len(self._editors)-1))
        else:
            self._rebuild_tabs()
        # Deleting a mecha is a change to the character
        self.state._on_var()

# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 6 — Summary
# ─────────────────────────────────────────────────────────────────────────────

class Page6Summary(tk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent, bg=BG)
        self.state  = state
        self._inner = None
        self._build_shell()

    def _build_shell(self):
        hdr = tk.Frame(self, bg=PANEL, pady=6)
        hdr.pack(fill="x", padx=8, pady=(8,0))
        tk.Label(hdr, text=t("label_char_summary","Character Summary"), bg=PANEL, fg=ACCENT,
                 font=("Georgia", 14, "bold")).pack(side="left", padx=12)
        mk_btn(hdr, t("btn_copy","📋 Copy"), self._copy_summary, bg=CARD, small=True
               ).pack(side="left", padx=8)
        outer, self._inner = scrollable(self, bg=BG)
        outer.pack(fill="both", expand=True)

    def _copy_summary(self):
        text = self._build_text_summary()
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo(t("msg_copied_title","Copied"), t("msg_copied_body","Summary copied to clipboard."))

    def _build_text_summary(self):
        s       = self.state
        d       = s.derived()
        formula = s.stat_formula.get()
        setting = s.skill_setting.get()
        fn      = STAT_FORMULAS[formula]
        af      = s.attr_formula.get()
        lines   = []
        W = 40

        def section(title):
            lines.append("")
            lines.append(title.upper())
            lines.append("─" * W)

        def row(label, value):
            lines.append(f"{label:<28}{value}")

        name = s.char_name.get()
        lines.append("=" * W)
        lines.append(f"  {name or 'Unnamed'}")
        lines.append("=" * W)

        section(t("section_core_values","Core Values"))
        row(t("label_stat_formula_row","Stat Formula"), display_name(formula))
        cp_ = t("label_cp","CP")
        row(f"{t('label_body','Body')} ({t('label_cp_cost_col','CP Cost')} {fn(int_or(s.body))} {cp_})", int_or(s.body))
        row(f"{t('label_mind','Mind')} ({t('label_cp_cost_col','CP Cost')} {fn(int_or(s.mind))} {cp_})", int_or(s.mind))
        row(f"{t('label_soul','Soul')} ({t('label_cp_cost_col','CP Cost')} {fn(int_or(s.soul))} {cp_})", int_or(s.soul))
        row(t("label_health_points","Health Points"), d["HP"])
        row(t("label_energy_points","Energy Points"), d["EP"])
        row(t("label_acv_long","Attack Combat Value"), d["ACV"])
        row(t("label_dcv_long","Defence Combat Value"), d["DCV"])
        row(t("label_shock_value","Shock Value"), d["SV"])

        section(t("section_char_points","Character Points"))
        cp_t = int_or(s.cp_total)
        cp_s = s.cp_spent()
        row(t("label_cp_total_row","CP total"), cp_t)
        row(t("label_cp_spent","CP spent"), cp_s)

        if s.attributes:
            section(t("section_attributes","Attributes"))
            for a in s.attributes:
                lv   = int_or(a["level"]); mod = int_or(a["modifier"])
                cost = attr_cost(a["base_cost"], lv, af) + mod
                desc = a["desc"].get()
                label = display_name(a["name"]) + (f" — {desc}" if desc else "")
                row(label, f"{t('label_lv_col','Lv')} {lv}  ({cost} {t('label_cp','CP')})")

        if s.defects:
            section(t("section_defects","Defects"))
            for di in s.defects:
                lv     = int_or(di["level"]); mod = int_or(di["modifier"])
                refund = attr_cost(di["base_cost"], lv, "Default") + mod
                desc   = di["desc"].get()
                label  = display_name(di["name"]) + (f" — {desc}" if desc else "")
                row(label, f"{t('label_lv_col','Lv')} {lv}  (-{refund} {t('label_cp','CP')})")

        if s.weapons:
            section(t("section_weapons","Weapons"))
            for i, w in enumerate(s.weapons):
                lv   = int_or(w["level"]); mod = int_or(w["modifier"])
                cost = weapon_cost(w, lv, mod, af)
                dmg  = weapon_damage(w, lv)
                wname = w["name"].get() or f"Weapon {i+1}"
                desc  = w["desc"].get()
                label = wname + (f" — {desc}" if desc else "")
                row(label, f"{t('label_lv_col','Lv')} {lv}  {t('label_dmg_abbr','Dmg')} {dmg}  ({cost} {t('label_cp','CP')})")

        section(f"{t('section_skill_points','Skill Points')}  [{t('label_setting_short','Setting:')} {display_name(setting)}]")
        sp_s = s.sp_spent()
        sp_t = s.sp_total_effective(d)
        row(t("label_total_sp","SP total"), sp_t)
        row(t("label_sp_spent","SP spent"), sp_s)
        row(t("label_total_sp","SP remaining"), f"{sp_t - sp_s:+d}")
        
        if s.skill_levels:
            active = [(n, v.get()) for n, v in s.skill_levels.items() if v.get() > 0]
            if active:
                section(t("section_skills","Skills"))
                for name_, lv in active:
                    c    = SKILLS[name_].get(setting, 0)
                    mod  = int_or(s.skill_mods[name_])
                    desc = s.skill_descs[name_].get()
                    label = display_name(name_) + (f" — {desc}" if desc else "")
                    row(label, f"{t('label_lv_col','Lv')} {lv}  ({lv*c + mod} {t('label_sp_display','SP:').rstrip(':')})")

        active_c = [(n, v.get()) for n, v in s.combat_levels.items() if v.get() > 0]
        if active_c:
            section(t("section_combat_skills","Combat Skills"))
            for name_, lv in active_c:
                c    = COMBAT_SKILLS[name_].get(setting, 0)
                mod  = int_or(s.combat_mods[name_])
                desc = s.combat_descs[name_].get()
                label = display_name(name_) + (f" — {desc}" if desc else "")
                row(label, f"{t('label_lv_col','Lv')} {lv}  ({lv*c + mod} {t('label_sp_display','SP:').rstrip(':')})")

        if s.mechas:
            for mecha in s.mechas:
                section(f"{t('label_mecha_prefix','Mecha:')} {mecha.name.get()}")
                row(t("label_hp_display","HP:").rstrip(":"), f"{mecha_hp(mecha)}")
                mp_t = int_or(mecha.mp_total); mp_s = mecha.mp_spent(af)
                row(t("label_mp_total_row","MP total"), mp_t)
                row(t("label_mp_spent","MP spent"), mp_s)
                for a in mecha.attributes:
                    lv   = int_or(a["level"]); mod = int_or(a["modifier"])
                    cost = attr_cost(a["base_cost"], lv, af) + mod
                    row(display_name(a["name"]), f"{t('label_lv_col','Lv')} {lv}  ({cost} {t('label_mp','MP')})")
                for i, w in enumerate(mecha.weapons):
                    lv   = int_or(w["level"]); mod = int_or(w["modifier"])
                    cost = weapon_cost(w, lv, mod, af)
                    dmg  = weapon_damage(w, lv)
                    wname = w["name"].get() or f"Weapon {i+1}"
                    row(wname, f"{t('label_lv_col','Lv')} {lv}  {t('label_dmg_abbr','Dmg')} {dmg}  ({cost} {t('label_mp','MP')})")
                for di in mecha.defects:
                    lv     = int_or(di["level"]); mod = int_or(di["modifier"])
                    refund = attr_cost(di["base_cost"], lv, "Default") + mod
                    row(display_name(di["name"]), f"{t('label_lv_col','Lv')} {lv}  (-{refund} {t('label_mp','MP')})")

        lines.append("")
        lines.append("=" * W)
        return "\n".join(lines)

    def refresh(self):
        for w in self._inner.winfo_children():
            w.destroy()
        s       = self.state
        d       = s.derived()
        formula = s.stat_formula.get()
        setting = s.skill_setting.get()
        fn      = STAT_FORMULAS[formula]

        def section(text):
            tk.Label(self._inner, text=text, bg=BG, fg=ACCENT,
                     font=("Georgia", 12, "bold"), anchor="w"
                     ).pack(fill="x", padx=16, pady=(12,2))
            tk.Frame(self._inner, bg=BORDER, height=1
                     ).pack(fill="x", padx=16, pady=(0,4))

        def row(label, value, fg=TEXT):
            f = tk.Frame(self._inner, bg=PANEL); f.pack(fill="x", padx=20, pady=1)
            tk.Label(f, text=label, bg=PANEL, fg=TEXT_DIM,
                     font=("Georgia", 9), width=28, anchor="w"
                     ).pack(side="left", padx=6)
            tk.Label(f, text=str(value), bg=PANEL, fg=fg,
                     font=("Courier", 10)).pack(side="left")

        def cp_row(label, info, cost_cp, fg=ACCENT2):
            f = tk.Frame(self._inner, bg=PANEL); f.pack(fill="x", padx=20, pady=1)
            tk.Label(f, text=label, bg=PANEL, fg=TEXT_DIM,
                     font=("Georgia", 9), width=28, anchor="w"
                     ).pack(side="left", padx=6)
            tk.Label(f, text=str(info), bg=PANEL, fg=TEXT,
                     font=("Courier", 9), width=12).pack(side="left")
            tk.Label(f, text=f"{cost_cp} {t('label_cp','CP')}", bg=PANEL, fg=fg,
                     font=("Courier", 9)).pack(side="left", padx=6)

        name = s.char_name.get()
        if name:
            tk.Label(self._inner, text=name, bg=BG, fg=TEXT,
                     font=("Georgia", 16, "bold"), anchor="w"
                     ).pack(fill="x", padx=16, pady=(12,0))

        section(t("section_core_values","Core Values"))
        row(t("label_stat_formula_row","Stat Formula"), display_name(formula))
        cp_row(t("label_body","Body"), int_or(s.body), fn(int_or(s.body)))
        cp_row(t("label_mind","Mind"), int_or(s.mind), fn(int_or(s.mind)))
        cp_row(t("label_soul","Soul"), int_or(s.soul), fn(int_or(s.soul)))
        row(t("label_health_points","Health"),         d["HP"],  GREEN)
        row(t("label_energy_points","Energy Points"),  d["EP"],  GREEN)
        row(t("label_acv_long","Attack Combat Value"), d["ACV"], GREEN)
        row(t("label_dcv_long","Defence Combat Value"),d["DCV"], GREEN)
        row(t("label_shock_value","Shock Value"),       d["SV"],  GREEN)

        section(t("section_char_points","Character Points"))
        cp_t = int_or(s.cp_total)
        cp_s = s.cp_spent()
        row(t("label_cp_total_row","CP total"), cp_t)
        row(t("label_cp_spent","CP spent"), cp_s)

        if s.attributes:
            section(t("section_attributes","Attributes"))
            af = s.attr_formula.get()
            for a in s.attributes:
                lv   = int_or(a["level"]); mod = int_or(a["modifier"])
                cost = attr_cost(a["base_cost"], lv, af) + mod
                desc = a["desc"].get()
                cp_row(display_name(a["name"]) + (f"  — {desc}" if desc else ""), f"Lv {lv}", cost)

        if s.defects:
            section(t("section_defects","Defects"))
            af = s.attr_formula.get()
            for di in s.defects:
                lv     = int_or(di["level"]); mod = int_or(di["modifier"])
                refund = attr_cost(di["base_cost"], lv, "Default") + mod
                desc   = di["desc"].get()
                cp_row(display_name(di["name"]) + (f"  — {desc}" if desc else ""),
                       f"Lv {lv}", f"-{refund}", fg=ACCENT3)

        if s.weapons:
            section(t("section_weapons","Weapons"))
            af = s.attr_formula.get()
            for i, w in enumerate(s.weapons):
                lv   = int_or(w["level"]); mod = int_or(w["modifier"])
                cost = weapon_cost(w, lv, mod, af)
                dmg  = weapon_damage(w, lv)
                desc = w["desc"].get()
                wname = w["name"].get() or f"Weapon {i+1}"
                label = wname + (f"  — {desc}" if desc else "")
                def _fmt_entries(lst):
                    parts = []
                    for e in lst:
                        n  = e[0] if isinstance(e, (list, tuple)) else e
                        lv = e[1] if isinstance(e, (list, tuple)) and len(e) > 1 else 1
                        dn = display_name(n)
                        parts.append(dn if lv == 1 else f"{dn} ×{lv}")
                    return ", ".join(parts) or "—"
                adv   = _fmt_entries(w["advantages"])
                defs  = _fmt_entries(w["defects"])
                f2 = tk.Frame(self._inner, bg=PANEL)
                f2.pack(fill="x", padx=20, pady=1)
                tk.Label(f2, text=label, bg=PANEL, fg=TEXT_DIM,
                         font=("Georgia", 9), width=28, anchor="w"
                         ).pack(side="left", padx=6)
                tk.Label(f2, text=f"Lv {lv}  Dmg {dmg}", bg=PANEL, fg=TEXT,
                         font=("Courier", 9)).pack(side="left", padx=4)
                tk.Label(f2, text=f"{cost} {t('label_cp','CP')}", bg=PANEL, fg=ACCENT2,
                         font=("Courier", 9)).pack(side="left", padx=6)
                sub = tk.Frame(self._inner, bg=PANEL); sub.pack(fill="x", padx=40)
                tk.Label(sub, text=f"{t('label_adv_short','Adv:')} {adv}", bg=PANEL, fg=GREEN,
                         font=("Georgia", 8), anchor="w").pack(side="left", padx=6)
                tk.Label(sub, text=f"{t('label_def_short','Def:')} {defs}", bg=PANEL, fg=ACCENT,
                         font=("Georgia", 8), anchor="w").pack(side="left", padx=6)

        section(t("section_skill_points","Skill Points"))
        sp_t = s.sp_total_effective(); sp_s = s.sp_spent()
        sp_base = int_or(s.sp_total); sp_bonus = d.get("SP_bonus", 0)
        row(t("label_base_sp","Base SP"), sp_base)
        if sp_bonus:
            row(t("label_sp_bonus","SP bonus"), f"+{sp_bonus}", GREEN)
        row(t("label_total_sp","Total SP available"), sp_t)
        row("SP spent", sp_s)

        active = [(n, v.get()) for n, v in s.skill_levels.items() if v.get()>0]
        if active:
            section(f"{t('section_skills','Skills')}  [{t('label_setting_short','Setting:')} {display_name(setting)}]")
            for name, lv in active:
                c    = SKILLS[name].get(setting, 0)
                mod  = int_or(s.skill_mods[name])
                desc = s.skill_descs[name].get()
                f = tk.Frame(self._inner, bg=PANEL); f.pack(fill="x", padx=20, pady=1)
                tk.Label(f, text=display_name(name)+(f" — {desc}" if desc else ""),
                         bg=PANEL, fg=TEXT_DIM, font=("Georgia", 9),
                         width=30, anchor="w").pack(side="left", padx=6)
                tk.Label(f, text=f"{t('label_lv_col','Lv')} {lv}", bg=PANEL, fg=TEXT,
                         font=("Courier", 9), width=6).pack(side="left")
                tk.Label(f, text=f"{lv*c + mod} {t('label_sp_display','SP:').rstrip(':')} ", bg=PANEL, fg=ACCENT2,
                         font=("Courier", 9)).pack(side="left", padx=6)

        active_c = [(n, v.get()) for n, v in s.combat_levels.items() if v.get()>0]
        if active_c:
            section("Combat Skills")
            for name, lv in active_c:
                data   = COMBAT_SKILLS[name]
                c      = data.get(setting, 0)
                mod    = int_or(s.combat_mods[name])
                is_atk = data.get("is_attack", True)
                desc   = s.combat_descs[name].get()
                bv     = d["ACV"] if is_atk else d["DCV"]
                btag   = "ACV"   if is_atk else "DCV"
                display = f"{t('label_lv_col','Lv')} {lv}  ({lv+bv} {t('label_with','with')} {btag})"
                f = tk.Frame(self._inner, bg=PANEL); f.pack(fill="x", padx=20, pady=1)
                tk.Label(f, text=display_name(name)+(f" — {desc}" if desc else ""),
                         bg=PANEL, fg=TEXT_DIM, font=("Georgia", 9),
                         width=30, anchor="w").pack(side="left", padx=6)
                tk.Label(f, text=display, bg=PANEL, fg=TEXT,
                         font=("Courier", 9), width=24).pack(side="left")
                tk.Label(f, text=f"{lv*c + mod} {t('label_sp_display','SP:').rstrip(':')} ", bg=PANEL, fg=ACCENT2,
                         font=("Courier", 9)).pack(side="left", padx=6)

        # ── Mecha ─────────────────────────────────────────────────────────
        if s.mechas:
            af = s.attr_formula.get()
            for mi, mecha in enumerate(s.mechas):
                mname = mecha.name.get() or f"Mecha {mi+1}"
                # Mecha header
                tk.Label(self._inner, text=f"⚙  {mname}", bg=BG, fg=ACCENT,
                         font=("Georgia", 13, "bold"), anchor="w"
                         ).pack(fill="x", padx=16, pady=(14, 0))
                tk.Frame(self._inner, bg=ACCENT, height=2
                         ).pack(fill="x", padx=16, pady=(1, 4))

                row("HP", f"{mecha_hp(mecha)}")
                mp_s = mecha.mp_spent(af); mp_t = int_or(mecha.mp_total)
                rem_mp = mp_t - mp_s
                row("MP total", mp_t)
                row("MP spent", mp_s)

                def mp_row(label, info, cost_mp, fg=ACCENT2):
                    f = tk.Frame(self._inner, bg=PANEL); f.pack(fill="x", padx=20, pady=1)
                    tk.Label(f, text=label, bg=PANEL, fg=TEXT_DIM,
                             font=("Georgia", 9), width=28, anchor="w"
                             ).pack(side="left", padx=6)
                    tk.Label(f, text=str(info), bg=PANEL, fg=TEXT,
                             font=("Courier", 9), width=12).pack(side="left")
                    tk.Label(f, text=f"{cost_mp} {t('label_mp','MP')}", bg=PANEL, fg=fg,
                             font=("Courier", 9)).pack(side="left", padx=6)

                if mecha.attributes:
                    tk.Label(self._inner, text=t("section_attributes","Attributes"), bg=BG, fg=ACCENT2,
                             font=("Georgia", 11, "bold"), anchor="w"
                             ).pack(fill="x", padx=20, pady=(8,2))
                    for a in mecha.attributes:
                        lv   = int_or(a["level"]); mod = int_or(a["modifier"])
                        cost = attr_cost(a["base_cost"], lv, af) + mod
                        desc = a["desc"].get()
                        mp_row(display_name(a["name"]) + (f"  — {desc}" if desc else ""), f"Lv {lv}", cost)

                if mecha.defects:
                    tk.Label(self._inner, text=t("section_defects","Defects"), bg=BG, fg=ACCENT3,
                             font=("Georgia", 11, "bold"), anchor="w"
                             ).pack(fill="x", padx=20, pady=(8,2))
                    for di in mecha.defects:
                        lv     = int_or(di["level"]); mod = int_or(di["modifier"])
                        refund = attr_cost(di["base_cost"], lv, "Default") + mod
                        desc   = di["desc"].get()
                        mp_row(display_name(di["name"]) + (f"  — {desc}" if desc else ""),
                               f"Lv {lv}", f"-{refund}", fg=ACCENT3)

                if mecha.weapons:
                    tk.Label(self._inner, text=t("section_weapons","Weapons"), bg=BG, fg=ACCENT,
                             font=("Georgia", 11, "bold"), anchor="w"
                             ).pack(fill="x", padx=20, pady=(8,2))
                    for wi, w in enumerate(mecha.weapons):
                        lv   = int_or(w["level"]); mod = int_or(w["modifier"])
                        cost = weapon_cost(w, lv, mod, af)
                        dmg  = weapon_damage(w, lv)
                        desc = w["desc"].get()
                        wname = w["name"].get() or f"Weapon {wi+1}"
                        label = wname + (f"  — {desc}" if desc else "")
                        def _fmt(lst):
                            parts = []
                            for e in lst:
                                n  = e[0] if isinstance(e,(list,tuple)) else e
                                lv2= e[1] if isinstance(e,(list,tuple)) and len(e)>1 else 1
                                dn = display_name(n)
                                parts.append(dn if lv2==1 else f"{dn} ×{lv2}")
                            return ", ".join(parts) or "—"
                        fw = tk.Frame(self._inner, bg=PANEL); fw.pack(fill="x", padx=20, pady=1)
                        tk.Label(fw, text=label, bg=PANEL, fg=TEXT_DIM,
                                 font=("Georgia", 9), width=28, anchor="w"
                                 ).pack(side="left", padx=6)
                        tk.Label(fw, text=f"Lv {lv}  Dmg {dmg}", bg=PANEL, fg=TEXT,
                                 font=("Courier", 9)).pack(side="left", padx=4)
                        tk.Label(fw, text=f"{cost} {t('label_mp','MP')}", bg=PANEL, fg=ACCENT2,
                                 font=("Courier", 9)).pack(side="left", padx=6)
                        sub = tk.Frame(self._inner, bg=PANEL); sub.pack(fill="x", padx=40)
                        tk.Label(sub, text=f"{t('label_adv_short','Adv:')} {_fmt(w['advantages'])}", bg=PANEL, fg=GREEN,
                                 font=("Georgia", 8), anchor="w").pack(side="left", padx=6)
                        tk.Label(sub, text=f"{t('label_def_short','Def:')} {_fmt(w['defects'])}", bg=PANEL, fg=ACCENT,
                                 font=("Georgia", 8), anchor="w").pack(side="left", padx=6)


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = BESMApp()
    if _LANG_CONFLICT_WARNING:
        app.after(200, lambda: messagebox.showwarning(
            "Multiple default languages", _LANG_CONFLICT_WARNING))
    app.mainloop()