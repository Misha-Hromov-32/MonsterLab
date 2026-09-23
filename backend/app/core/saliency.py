"""Предсказание внимания: карта плотности вероятности того, куда посмотрит человек.

DeepGaze IIE (Linardos, Kümmerer et al., ICCV 2021) — ансамбль CNN, обученный на реальных
записях движения глаз (MIT1003 + SALICON). Основной движок, если установлен torch.

Классический движок — запасной, без нейросетей: многомасштабный спектральный остаток
(Hou & Zhang, 2007) + цветовой контраст «центр–окружение» в Lab + смещение к центру кадра.

Оба возвращают карту тех же пропорций, что и картинка, с суммой = 1.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import warnings

import cv2
import numpy as np

from .. import config
from .imaging import resize_long

log = logging.getLogger(__name__)

CLASSIC_SIDE = 256
DEEPGAZE_MIN_SHORT = 192  # меньше — свёртки бэкбонов не помещаются


def _normalize01(a: np.ndarray) -> np.ndarray:
    mn, mx = float(a.min()), float(a.max())
    return (a - mn) / (mx - mn) if mx > mn else np.zeros_like(a)


def center_prior(h: int, w: int, sx: float = 0.30, sy: float = 0.32, uniform: float = 0.2) -> np.ndarray:
    """Смещение взгляда к центру: гауссиана + равномерная подложка, сумма = 1."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    g = np.exp(-(((xs - (w - 1) / 2) / (sx * w)) ** 2 + ((ys - (h - 1) / 2) / (sy * h)) ** 2) / 2)
    g /= g.sum()
    return (1 - uniform) * g + uniform / (h * w)


# ---------------------------------------------------------------- классический движок


def _spectral_residual(gray: np.ndarray) -> np.ndarray:
    f = np.fft.fft2(gray)
    log_amp = np.log(np.abs(f) + 1e-8)
    residual = log_amp - cv2.blur(log_amp, (3, 3))
    sal = np.abs(np.fft.ifft2(np.exp(residual + 1j * np.angle(f)))) ** 2
    return cv2.GaussianBlur(sal.astype(np.float32), (0, 0), max(1.0, 0.025 * max(gray.shape)))


def classic_density(rgb: np.ndarray) -> np.ndarray:
    work = resize_long(rgb, CLASSIC_SIDE)
    h, w = work.shape[:2]
    lab = cv2.cvtColor(work, cv2.COLOR_RGB2LAB).astype(np.float32)
    diag = np.hypot(h, w)

    # 1) спектральный остаток на трёх масштабах — «что выбивается из фона»
    sr = np.zeros((h, w), np.float32)
    for side in (64, 128, 256):
        small = resize_long(lab[..., 0], side)
        sr += cv2.resize(_normalize01(_spectral_residual(small)), (w, h))
    sr = _normalize01(sr)

    # 2) цветовой контраст центр–окружение в Lab (как в модели Itti–Koch)
    col = np.zeros((h, w), np.float32)
    for c, s in ((0.01, 0.06), (0.02, 0.12), (0.04, 0.24)):
        center = cv2.GaussianBlur(lab, (0, 0), c * diag)
        surround = cv2.GaussianBlur(lab, (0, 0), s * diag)
        col += _normalize01(np.linalg.norm(center - surround, axis=2))
    # 3) глобальная редкость цвета: насколько пиксель отличается от среднего цвета кадра
    rarity = np.linalg.norm(lab - lab.reshape(-1, 3).mean(0), axis=2)
    col = _normalize01(col) * 0.7 + _normalize01(cv2.GaussianBlur(rarity, (0, 0), 0.02 * diag)) * 0.3

    feat = cv2.GaussianBlur(0.5 * sr + 0.5 * col, (0, 0), 0.02 * diag)
    feat = _normalize01(feat) ** 1.6  # усиливаем пики, как у реальных карт фиксаций
    prior = center_prior(h, w)
    dens = feat * prior
    total = float(dens.sum())
    # однотонная картинка: зацепиться не за что — взгляд просто идёт в центр
    return dens / total if total > 0 else prior


# ---------------------------------------------------------------- DeepGaze IIE


class DeepGaze:
    def __init__(self) -> None:
        self.model = None
        self.torch = None
        self.error: str | None = None
        self._lock = threading.Lock()  # модель не потокобезопасна, и так быстрее, чем параллельно

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        try:
            warnings.filterwarnings("ignore", category=UserWarning, module="torchvision")
            import torch
            from deepgaze_pytorch import DeepGazeIIE

            # По числу физических ядер: при гипертрединге (все логические ядра) инференс
            # замедляется в 15–30 раз из-за конкуренции потоков OpenMP. На маленьких VPS
            # (1–2 vCPU) делить нечего — берём все ядра, иначе вдвое медленнее.
            cpus = os.cpu_count() or 2
            torch.set_num_threads(config.TORCH_THREADS or (cpus if cpus <= 2 else cpus // 2))
            started = time.perf_counter()
            self.model = DeepGazeIIE(pretrained=True).eval()
            self.torch = torch
            log.info("DeepGaze IIE загружен за %.1f с", time.perf_counter() - started)
        except ImportError as exc:  # лёгкий образ (NEURAL=0) — это не ошибка
            self.error = f"{type(exc).__name__}: {exc}"
            log.info("Нейросеть не установлена, работает классический движок")
        except Exception as exc:  # noqa: BLE001 — нет весов, битый файл: работаем без нейросети
            self.error = f"{type(exc).__name__}: {exc}"
            log.warning("DeepGaze недоступен, работает классический движок: %s", self.error)

    def density(self, rgb: np.ndarray, side: int) -> np.ndarray:
        torch = self.torch
        work = resize_long(rgb, side)
        h, w = work.shape[:2]
        # очень вытянутые баннеры дополняем полями цвета края, потом обрезаем карту обратно
        ph, pw = max(0, DEEPGAZE_MIN_SHORT - h), max(0, DEEPGAZE_MIN_SHORT - w)
        if ph or pw:
            work = cv2.copyMakeBorder(work, ph // 2, ph - ph // 2, pw // 2, pw - pw // 2, cv2.BORDER_REPLICATE)
        big_h, big_w = work.shape[:2]
        prior = np.log(center_prior(big_h, big_w)).astype(np.float32)
        x = torch.tensor(work.transpose(2, 0, 1)[None].copy(), dtype=torch.float32)
        with self._lock, torch.inference_mode():
            log_d = self.model(x, torch.tensor(prior[None]))[0, 0].numpy()
        log_d = log_d[ph // 2 : ph // 2 + h, pw // 2 : pw // 2 + w]
        d = np.exp(log_d - log_d.max()).astype(np.float32)
        return d / d.sum()


deepgaze = DeepGaze()


def load() -> None:
    """Вызывается при старте приложения. ENGINE=classic — нейросеть не грузим вовсе."""
    if config.ENGINE != "classic":
        deepgaze.load()


def density(rgb: np.ndarray) -> np.ndarray:
    """Карта внимания лучшим доступным движком."""
    if deepgaze.ready:
        try:
            return deepgaze.density(rgb, config.DEEPGAZE_SIDE)
        except Exception:  # сбой нейросети не должен ронять анализ
            log.exception("DeepGaze упал на картинке %s, считаю классическим движком", rgb.shape)
    return classic_density(rgb)
