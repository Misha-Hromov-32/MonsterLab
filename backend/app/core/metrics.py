"""Метрики обложки поверх карты внимания и самого изображения.

Каждая метрика — измеримая величина с понятным смыслом, а не «магическая оценка».
Шкалы 0–100 откалиброваны на типичных карточках маркетплейсов: пороги шкал — константы ниже,
пороги выводов — NOTE_* там же. Цвет шкал в интерфейсе — отдельная, более грубая градация
(frontend/src/lib/constants.ts: SCORE_GOOD / SCORE_WARN), подсказки инспектора повторяют NOTE_*.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage

from .imaging import resize_long, resize_to

# Итоговый индекс — взвешенная сумма четырёх оценок.
WEIGHTS = {"focus": 0.35, "clarity": 0.25, "thumb": 0.25, "contrast": 0.15}

# Фокус: половина внимания на 4% площади -> 100, на 22% -> 0; каждая зона сверх трёх — минус 7.
FOCUS_AREA50 = (0.22, 0.04)
FOCUS_FREE_SPOTS = 3
FOCUS_SPOT_PENALTY = 7
# Ясность: 3 элемента -> чисто, 16 -> перегруз; 7 заметных цветов -> спокойно, 22 -> пёстро.
CLARITY_ELEMENTS = (16, 3)
CLARITY_COLORS = (22, 7)
# RMS-контраст яркости 0.08 -> плоско, 0.28 -> сочно.
CONTRAST_RMS = (0.08, 0.28)
# Взвешенный SSIM после уменьшения до превью: 0.45 -> каша, 0.85 -> всё читается.
THUMB_SSIM = (0.45, 0.85)

THUMB_WIDTH = 170  # ширина карточки в мобильной выдаче, CSS-пиксели

# Когда оценка превращается в вывод «плохо» / «хорошо».
NOTE_FOCUS = (40, 70)
NOTE_CLARITY = (25, 45)  # ниже первого — «плохо», ниже второго — «внимание»
NOTE_THUMB = (45, 75)
NOTE_CONTRAST = 35


def _clamp(v: float, lo: float = 0, hi: float = 100) -> float:
    return float(min(hi, max(lo, v)))


def scale(v: float, bad: float, good: float) -> int:
    """Линейно переводит величину в 0–100: bad -> 0, good -> 100 (в любую сторону)."""
    return round(_clamp((v - bad) / (good - bad) * 100))


# ---------------------------------------------------------------- внимание


def mass_area(dens: np.ndarray, mass: float) -> float:
    """Минимальная доля площади, на которую приходится `mass` внимания."""
    flat = np.sort(dens.ravel())[::-1]
    k = int(np.searchsorted(np.cumsum(flat), mass * flat.sum())) + 1
    return min(k, flat.size) / flat.size


def hotspots(dens: np.ndarray, mass: float = 0.6, min_area: float = 0.004) -> int:
    """Число отдельных «горячих» зон, которые вместе забирают `mass` внимания.

    Пятна меньше `min_area` кадра (0,4%) — шум карты, а не зона, за которую спорит взгляд.
    """
    d = resize_long(dens, 128)
    flat = np.sort(d.ravel())[::-1]
    thr = flat[min(flat.size - 1, int(np.searchsorted(np.cumsum(flat), mass * flat.sum())))]
    labels, n = ndimage.label(d >= thr, structure=np.ones((3, 3)))
    if n == 0:
        return 0
    sizes = ndimage.sum(np.ones_like(d), labels, index=range(1, n + 1))
    return int((np.asarray(sizes) >= min_area * d.size).sum())


def fixations(dens: np.ndarray, k: int = 5) -> list[dict]:
    """Вероятный порядок первых фиксаций: жадный выбор пиков с «торможением возврата»
    (inhibition of return) — после фиксации зона гасится гауссианой."""
    d = resize_long(dens, 128).astype(np.float64)
    h, w = d.shape
    d = cv2.GaussianBlur(d, (0, 0), 0.02 * max(h, w))  # сглаживаем, чтобы не цепляться за шум
    total = d.sum() or 1.0
    ys, xs = np.mgrid[0:h, 0:w]
    sigma = 0.09 * max(h, w)  # радиус зоны, которую глаз охватывает за одну фиксацию
    out: list[dict] = []
    first_peak = None
    for _ in range(k):
        y, x = divmod(int(np.argmax(d)), w)
        peak = d[y, x]
        if first_peak is None:
            first_peak = peak
        elif peak < 0.12 * first_peak:  # пик слабее 12% первого — уже фон, а не фиксация
            break
        g = np.exp(-((xs - x) ** 2 + (ys - y) ** 2) / (2 * sigma**2))
        out.append({"x": (x + 0.5) / w, "y": (y + 0.5) / h, "mass": round(float((d * g).sum() / total), 4)})
        d = d * (1 - g)
    return out


# ---------------------------------------------------------------- изображение


def complexity(rgb: np.ndarray) -> dict:
    """Визуальный перегруз = число отдельных элементов + число заметных цветов.

    Элементы ищем как связные области контуров: плашка, надпись, товар, иконка.
    Текстура на фото сливается в одну область, поэтому шумом не считается.
    """
    work = resize_long(rgb, 384)
    gray = cv2.cvtColor(work, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 50, 140)
    blob = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(blob, connectivity=8)
    # области меньше 0,15% кадра — буквы и соринки, а не отдельные элементы
    elements = int((stats[1:, cv2.CC_STAT_AREA] >= 0.0015 * blob.size).sum()) if n > 1 else 0

    # цвета: квантуем Lab на 8×8×8 корзин и считаем те, что занимают больше 0.8% кадра
    lab = cv2.cvtColor(work, cv2.COLOR_RGB2LAB).astype(np.int32) // 32
    bins = lab[..., 0] * 64 + lab[..., 1] * 8 + lab[..., 2]
    colors = int((np.bincount(bins.ravel(), minlength=512) / bins.size > 0.008).sum())

    # число элементов перегружает сильнее, чем пестрота, — отсюда веса 0.7 / 0.3
    clarity = 0.7 * scale(elements, *CLARITY_ELEMENTS) + 0.3 * scale(colors, *CLARITY_COLORS)
    return {"elements": elements, "colors": colors, "clarity": round(clarity)}


def contrast(rgb: np.ndarray) -> float:
    """RMS-контраст яркости, 0–1."""
    lab = cv2.cvtColor(resize_long(rgb, 512), cv2.COLOR_RGB2LAB)
    return float(lab[..., 0].std() / 255)


def _ssim_map(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a, b = a.astype(np.float64), b.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2

    def blur(z: np.ndarray) -> np.ndarray:
        return cv2.GaussianBlur(z, (0, 0), 1.5)

    ma, mb = blur(a), blur(b)
    va, vb, cov = blur(a * a) - ma**2, blur(b * b) - mb**2, blur(a * b) - ma * mb
    return ((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma**2 + mb**2 + c1) * (va + vb + c2))


def thumbnail_survival(rgb: np.ndarray) -> float:
    """Сколько структуры переживает уменьшение до размера карточки в выдаче.

    Мелкий текст и детали пропадают первыми, поэтому SSIM падает. Считаем его только там,
    где есть детали: гладкий фон и так переживёт уменьшение и не должен «разбавлять» потерю.
    """
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # эталон — превью на экране с плотностью 3x; сторона ограничена, чтобы узкие баннеры
    # не превращались в полотно на десятки тысяч пикселей
    ref_w = THUMB_WIDTH * 3
    ref_h = min(max(1, round(h * ref_w / w)), ref_w * 4)
    ref = resize_to(gray, ref_w, ref_h)
    small = resize_to(gray, THUMB_WIDTH, max(1, round(ref_h * THUMB_WIDTH / ref_w)))
    back = cv2.resize(small, (ref.shape[1], ref.shape[0]), interpolation=cv2.INTER_LINEAR)
    ref32 = ref.astype(np.float32)
    grad = cv2.magnitude(cv2.Sobel(ref32, cv2.CV_32F, 1, 0), cv2.Sobel(ref32, cv2.CV_32F, 0, 1))
    weight = cv2.GaussianBlur(grad, (0, 0), 2)
    if weight.sum() < 1e-6:
        return 1.0
    return float((_ssim_map(ref, back) * weight).sum() / weight.sum())


def palette(rgb: np.ndarray, k: int = 5) -> list[dict]:
    """Основные цвета обложки (k-means в Lab), от самого большого по площади."""
    lab = cv2.cvtColor(resize_long(rgb, 96), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    cv2.setRNGSeed(7)  # детерминированный результат для одной и той же картинки
    _, labels, centers = cv2.kmeans(lab, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    shares = np.bincount(labels.ravel(), minlength=k) / labels.size
    rgb_c = cv2.cvtColor(centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(-1, 3)
    return [
        {"hex": "#{:02x}{:02x}{:02x}".format(*(int(c) for c in rgb_c[i])), "share": round(float(shares[i]), 3)}
        for i in np.argsort(-shares)
    ]


# ---------------------------------------------------------------- сводка


def analyze(rgb: np.ndarray, dens: np.ndarray) -> dict:
    area50 = mass_area(dens, 0.5)
    spots = hotspots(dens)
    cx = complexity(rgb)
    rms = contrast(rgb)
    ssim = thumbnail_survival(rgb)

    extra_spots = max(0, spots - FOCUS_FREE_SPOTS)
    scores = {
        "focus": round(_clamp(scale(area50, *FOCUS_AREA50) - extra_spots * FOCUS_SPOT_PENALTY)),
        "clarity": cx["clarity"],
        "contrast": scale(rms, *CONTRAST_RMS),
        "thumb": scale(ssim, *THUMB_SSIM),
    }
    raw = {
        "area50": round(area50, 4),
        "hotspots": spots,
        "elements": cx["elements"],
        "colors": cx["colors"],
        "rms_contrast": round(rms, 4),
        "thumb_ssim": round(ssim, 4),
    }
    index = round(sum(scores[k] * w for k, w in WEIGHTS.items()))
    return {"index": index, "scores": scores, "raw": raw, "notes": notes(scores, raw)}


def notes(s: dict, r: dict) -> list[dict]:
    """Выводы простыми словами: что хорошо, что мешает и как исправить."""
    out: list[dict] = []

    def add(level: str, title: str, text: str) -> None:
        out.append({"level": level, "title": title, "text": text})

    a50 = round(r["area50"] * 100)
    if s["focus"] < NOTE_FOCUS[0]:
        add(
            "bad",
            "Внимание рассеяно",
            f"Половина взгляда размазана по {a50}% площади. Оставьте один главный акцент — "
            "товар или оффер — и уберите конкурирующие элементы.",
        )
    elif s["focus"] >= NOTE_FOCUS[1]:
        add(
            "good",
            "Сильный фокус",
            f"Половина внимания собрана на {a50}% площади — взгляд сразу понимает, куда смотреть.",
        )
    if r["hotspots"] > FOCUS_FREE_SPOTS:
        add(
            "warn",
            f"{r['hotspots']} зон спорят за взгляд",
            "Больше трёх центров внимания — признак перегруза. "
            "Сгруппируйте бенефиты или уберите второстепенные плашки.",
        )
    if s["clarity"] < NOTE_CLARITY[1]:
        add(
            "bad" if s["clarity"] < NOTE_CLARITY[0] else "warn",
            "Визуальный перегруз",
            f"На обложке ~{r['elements']} отдельных элементов и {r['colors']} заметных цветов. "
            "Мозг считывает 3–5 объектов за раз: оставьте товар, главный оффер и 1–2 бенефита.",
        )
    if s["thumb"] < NOTE_THUMB[0]:
        add(
            "bad",
            "Детали не переживут выдачу",
            "В маленькой карточке в ленте телефона мелкий текст станет нечитаемым. "
            "Укрупните надписи — минимум до 6–7% высоты обложки.",
        )
    elif s["thumb"] >= NOTE_THUMB[1]:
        add("good", "Читается на превью", "Крупные формы сохраняются даже в маленькой карточке выдачи.")
    if s["contrast"] < NOTE_CONTRAST:
        add(
            "warn",
            "Низкий контраст",
            "Картинка «плоская» по яркости. Отделите товар от фона светом, тенью или контрастной подложкой.",
        )
    return out
