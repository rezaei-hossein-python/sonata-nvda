# Redistribution checklist

| Component | License | Redistribution notes |
| --- | --- | --- |
| Sonata NVDA add-on | GPL v2 | Publish source and preserve original copyright and license notices. |
| `sonata-grpc` | MIT; bundled components have additional terms | Preserve the shipped Sonata, ONNX Runtime, and eSpeak NG notices. |
| eSpeak NG in the backend | GPL v3 | Preserve its bundled license and source availability obligations. |
| ONNX Runtime | MIT plus third-party notices | Preserve the bundled license and third-party notice inventory. |
| grpcio | Apache 2.0 | Preserve applicable notices. |
| protobuf | BSD-3-Clause | Preserve applicable notices. |
| miniaudio and cffi | MIT | Preserve applicable notices. |
| psutil | BSD-3-Clause | Preserve applicable notices. |
| Offline Piper starter models | Public domain or CC BY 4.0 | Preserve every `MODEL_CARD` and `addon/starterVoices/LICENSES.md`. |

The four starter voice models are intentionally bundled release assets. Their
sources, attribution requirements, and redistribution conclusions are recorded
in `addon/starterVoices/LICENSES.md` and their exact payload hashes are recorded
in `addon/starterVoices/manifest.json`.
