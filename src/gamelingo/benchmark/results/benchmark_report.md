# Translation Engine Benchmark Report

## Environment
- Dataset: Synthetic Japanese-English (60 strings)
- Hardware: Detected at runtime

## Candidates
### OPUS-MT (Helsinki-NLP) via Transformers
- **Status**: success
- **Version**: opus-mt-ja-en
- **Model License**: CC-BY 4.0 / MIT
- **Code License**: Apache 2.0 (Transformers)
- **Load Time**: 95.36s
- **Throughput**: 7.75 strings/s (44.59 chars/s)
- **Placeholder Failures**: 0

### Argos Translate
- **Status**: success
- **Version**: 1.1 (translate-ja_en)
- **Model License**: CC0
- **Code License**: MIT
- **Load Time**: 27.12s
- **Throughput**: 27.98 strings/s (160.86 chars/s)
- **Placeholder Failures**: 1

### OPUS-MT via CTranslate2
- **Status**: failed
- **Version**: opus-mt-ja-en (ct2)
- **Model License**: CC-BY 4.0 / MIT
- **Code License**: MIT (CTranslate2)
- **Error**: CTranslate2 manual conversion step required.
