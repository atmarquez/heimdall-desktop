#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Show_Alert.py — Ventana de aviso simple para usar con el Programador de tareas

USO BÁSICO
----------
python Show_Alert.py "<mensaje>"
    [-Sound None|Asterisk|Beep|Exclamation|Hand|Question]
    [-Icon None|Info|Information|Warning|Error|Question]
    [-Attention None|Blink|Flash]
    [-BlinkSeconds N]

COMPORTAMIENTO POR DEFECTO
-------------------------
- Sin texto
- Sin sonido
- Sin icono
- Un único botón "Ok"
"""

import argparse
import sys
import tkinter as tk
from tkinter import ttk
import winsound
import ctypes
from ctypes import wintypes

# ------------------------------------------------------------
# CONSTANTES FlashWindowEx
# ------------------------------------------------------------

FLASHW_STOP = 0
FLASHW_CAPTION = 1
FLASHW_TRAY = 2
FLASHW_ALL = 3
FLASHW_TIMER = 4
FLASHW_TIMERNOFG = 12


class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwnd", wintypes.HWND),
        ("dwFlags", wintypes.UINT),
        ("uCount", wintypes.UINT),
        ("dwTimeout", wintypes.UINT),
    ]


user32 = ctypes.windll.user32


# ------------------------------------------------------------
# PARSEO DE ARGUMENTOS
# ------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("message", nargs="?", default="", help="Texto del mensaje")

    parser.add_argument(
        "-Sound",
        choices=["None", "Asterisk", "Beep", "Exclamation", "Hand", "Question"],
        default="None",
    )

    parser.add_argument(
        "-Icon",
        choices=["None", "Info", "Information", "Warning", "Error", "Question"],
        default="None",
    )

    parser.add_argument(
        "-Attention",
        choices=["None", "Blink", "Flash"],
        default="None",
    )

    parser.add_argument(
        "-BlinkSeconds",
        type=int,
        default=6,
        help="Duración del parpadeo (Blink)",
    )

    return parser.parse_args()


# ------------------------------------------------------------
# SONIDOS DEL SISTEMA
# ------------------------------------------------------------

def play_sound(sound):
    if sound == "Asterisk":
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    elif sound == "Beep":
        winsound.MessageBeep(winsound.MB_OK)
    elif sound == "Exclamation":
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    elif sound == "Hand":
        winsound.MessageBeep(winsound.MB_ICONHAND)
    elif sound == "Question":
        winsound.MessageBeep(winsound.MB_ICONQUESTION)


# ------------------------------------------------------------
# FLASH DE BARRA DE TÍTULO / TASKBAR
# ------------------------------------------------------------

def flash_window(hwnd):
    fi = FLASHWINFO()
    fi.cbSize = ctypes.sizeof(FLASHWINFO)
    fi.hwnd = hwnd
    fi.dwFlags = FLASHW_TIMERNOFG
    fi.uCount = 0
    fi.dwTimeout = 0
    user32.FlashWindowEx(ctypes.byref(fi))


def stop_flash(hwnd):
    fi = FLASHWINFO()
    fi.cbSize = ctypes.sizeof(FLASHWINFO)
    fi.hwnd = hwnd
    fi.dwFlags = FLASHW_STOP
    fi.uCount = 0
    fi.dwTimeout = 0
    user32.FlashWindowEx(ctypes.byref(fi))


# ------------------------------------------------------------
# VENTANA PRINCIPAL
# ------------------------------------------------------------

def main():
    args = parse_args()

    root = tk.Tk()
    root.title("Aviso")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    # Centrar ventana
    root.update_idletasks()
    root.geometry("+{}+{}".format(
        (root.winfo_screenwidth() // 2) - 200,
        (root.winfo_screenheight() // 2) - 100
    ))

    # Contenedor principal
    main_frame = ttk.Frame(root, padding=12)
    main_frame.pack(fill="both", expand=True)

    content = ttk.Frame(main_frame)
    content.pack(fill="x")

    # --------------------------------------------------------
    # ICONO
    # --------------------------------------------------------

    icon_label = None

    icon_map = {
        "Info": "info",
        "Information": "info",
        "Warning": "warning",
        "Error": "error",
        "Question": "question",
    }

    if args.Icon != "None":
        icon_label = ttk.Label(content)
        icon_label.pack(side="left", padx=(0, 10))
        root.iconbitmap(default="")  # evita warning

        try:
            root.iconbitmap(sys.executable)
        except Exception:
            pass

    # --------------------------------------------------------
    # TEXTO
    # --------------------------------------------------------

    message_label = ttk.Label(
        content,
        text=args.message,
        wraplength=600,
        font=("Segoe UI", 11),
        justify="left",
    )
    message_label.pack(side="left")

    # --------------------------------------------------------
    # BOTONES
    # --------------------------------------------------------

    buttons = ttk.Frame(main_frame)
    buttons.pack(fill="x", pady=(10, 0))

    ok_button = ttk.Button(buttons, text="Ok", command=root.destroy)
    ok_button.pack(side="right")
    root.bind("<Return>", lambda e: root.destroy())

    # --------------------------------------------------------
    # SONIDO
    # --------------------------------------------------------

    if args.Sound != "None":
        try:
            play_sound(args.Sound)
        except Exception:
            pass

    # --------------------------------------------------------
    # ATENCIÓN: BLINK
    # --------------------------------------------------------

    default_bg = root.cget("background")
    blink_color = "#FFFFC8"
    blink_interval = 400
    elapsed = 0

    def blink():
        nonlocal elapsed
        current = root.cget("background")
        root.configure(background=blink_color if current == default_bg else default_bg)
        elapsed += blink_interval
        if elapsed < args.BlinkSeconds * 1000:
            root.after(blink_interval, blink)
        else:
            root.configure(background=default_bg)

    if args.Attention == "Blink":
        root.after(0, blink)

    # --------------------------------------------------------
    # ATENCIÓN: FLASH
    # --------------------------------------------------------

    if args.Attention == "Flash":
        root.after(100, lambda: flash_window(root.winfo_id()))
        root.bind("<FocusIn>", lambda e: stop_flash(root.winfo_id()))

    # --------------------------------------------------------
    # MOSTRAR (MODAL)
    # --------------------------------------------------------

    root.mainloop()


if __name__ == "__main__":
    main()
