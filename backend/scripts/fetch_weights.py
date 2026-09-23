"""Скачивает веса DeepGaze IIE в TORCH_HOME и проверяет, что модель из них собирается.

Если загрузка оборвалась, torch.hub оставляет обрезанный файл, и дальше модель не грузится
(«unexpected EOF»). Здесь битые файлы находятся и удаляются, после чего загрузка повторяется.

Используется при сборке Docker-образа. Код выхода 0 — всё готово.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ATTEMPTS = 3


def drop_broken(checkpoints: Path) -> int:
    import torch

    removed = 0
    for f in checkpoints.glob("*"):
        if not f.is_file():
            continue
        try:
            # файлы только что скачаны самим torch.hub из официальных источников DeepGaze и torchvision
            torch.load(f, map_location="cpu", weights_only=False)
        except Exception:  # noqa: BLE001 — любая ошибка чтения значит, что файл битый
            print(f"  битый файл, удаляю: {f.name}", flush=True)
            f.unlink(missing_ok=True)
            removed += 1
    return removed


def main() -> int:
    if not os.environ.get("TORCH_HOME"):
        print("Задайте TORCH_HOME — папку, куда складывать веса", file=sys.stderr)
        return 2
    checkpoints = Path(os.environ["TORCH_HOME"]) / "hub" / "checkpoints"

    from deepgaze_pytorch import DeepGazeIIE

    for attempt in range(1, ATTEMPTS + 1):
        try:
            DeepGazeIIE(pretrained=True).eval()
            print("  веса загружены и проверены", flush=True)
            return 0
        except Exception as exc:  # noqa: BLE001 — сеть, битый файл, нет места: пробуем ещё раз
            print(f"  попытка {attempt} не удалась: {type(exc).__name__}: {str(exc)[:160]}", flush=True)
            drop_broken(checkpoints)
            time.sleep(3 * attempt)
    return 1


if __name__ == "__main__":
    sys.exit(main())
