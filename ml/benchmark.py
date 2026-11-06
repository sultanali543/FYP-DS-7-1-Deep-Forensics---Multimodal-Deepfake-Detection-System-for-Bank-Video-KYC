"""A small CPU timing check. Synthetic inputs cannot measure deepfake accuracy."""

import time

from .common import configure_torch, runtime_versions
from .features import BACKBONES, make_encoder


def benchmark_encoders(batch_size=4, repeats=5):
    import psutil

    torch = configure_torch(2)
    torch.manual_seed(42)
    inputs = torch.rand(batch_size, 3, 224, 224)
    results = []
    for name in BACKBONES:
        encoder, _, dimension = make_encoder(name)
        with torch.inference_mode():
            encoder(inputs)  # Warm up before measuring.
            started = time.perf_counter()
            for _ in range(repeats):
                vectors = encoder(inputs)
            elapsed = time.perf_counter() - started
        if vectors.shape != (batch_size, dimension) or not torch.isfinite(vectors).all():
            raise ValueError("Encoder smoke check failed.")
        results.append({"backbone": name, "feature_dimension": dimension,
                        "encoder_parameters": sum(value.numel() for value in encoder.parameters()),
                        "images_per_second": batch_size * repeats / elapsed,
                        "seconds_per_12_faces": 12 * elapsed / (batch_size * repeats),
                        "process_ram_mb": psutil.Process().memory_info().rss / 1024**2})
        del encoder
    return {"device": "cpu", "threads": 2, "batch_size": batch_size, "repeats": repeats,
            "runtime_versions": runtime_versions(), "results": results,
            "scope": "Synthetic tensors measure encoder speed only. Video decoding and face detection are excluded.",
            "accuracy_measured": False}
