"""Разрешённые модели генератора и цена одного готового изображения в импульсах."""

from .. import config

MODELS = {
    "openai/gpt-image-2.6-flare": ("GPT Image 2.6 Flare", 65),
    "openai/gpt-image-2.6-sunburst": ("GPT Image 2.6 Sunburst", 70),
    "openai/gpt-image-2": ("GPT Image 2", 85),
    "bytedance-seed/seedream-5-5": ("Seedream 5.5", 30),
    "krea/k3-edit": ("Krea K3 Edit", 35),
    "microsoft/mai-image-2.7": ("MAI Image 2.7", 60),
    "black-forest-labs/flux-3-image": ("FLUX.3 Image", 25),
    "black-forest-labs/flux-3-image-klein": ("FLUX.3 Image Klein", 10),
    "google/gemini-3.1-flash-image": ("Nano Banana 2", 115),
    "google/gemini-3-pro-image": ("Nano Banana Pro", 210),
}


def default_id():
    return config.IMAGE_MODEL if config.IMAGE_MODEL in MODELS else next(iter(MODELS))


def cost(model):
    base = MODELS[model][1]
    return base * 4 if model.startswith("openai/") and config.IMAGE_QUALITY == "high" else base


def catalog():
    return [{"id": key, "title": title, "cost": cost(key)} for key, (title, _) in MODELS.items()]
