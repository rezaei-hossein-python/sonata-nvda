# Offline starter voice licenses and attribution

The starter models are unmodified data works obtained from the
[Piper voices v1.0.0 catalog](https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0).
Each model's original `MODEL_CARD` is retained beside its model and configuration
file. All four model cards state that the voice was trained from scratch, so no
separate base-model license chain applies.

| Voice | Source and attribution | License | Attribution required | Redistribution |
| --- | --- | --- | --- | --- |
| `en_US-ljspeech-medium` | [LJ Speech Dataset](https://keithito.com/LJ-Speech-Dataset/), recordings by Linda Johnson; alignment and annotation by Keith Ito | Public domain | No; source credit retained | Allowed |
| `fr_FR-mls-medium` | [Multilingual LibriSpeech](https://www.openslr.org/94/), Vineel Pratap, Qiantong Xu, Anuroop Sriram, Gabriel Synnaeve, and Ronan Collobert | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Yes; this table and the model card provide credit and a license link | Allowed with attribution |
| `de_DE-mls-medium` | [Multilingual LibriSpeech](https://www.openslr.org/94/), Vineel Pratap, Qiantong Xu, Anuroop Sriram, Gabriel Synnaeve, and Ronan Collobert | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Yes; this table and the model card provide credit and a license link | Allowed with attribution |
| `es_ES-carlfm-x_low` | [Carlfm public-domain speech datasets](https://github.com/carlfm01/my-speech-datasets) | Public domain | No; source credit retained | Allowed |

The files were repackaged without modifying model weights. Installation copies
the verified files into the NVDA configuration voice directory. The package's
`manifest.json` records the exact size and SHA-256 hash of every model, model
configuration, and model card.
