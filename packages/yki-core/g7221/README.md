# MoonBit Siren7 / G.722.1-derived codec

The YKI profile is mono s16le PCM at 16 kHz / 16 kbps. Each 20 ms frame has
320 samples (640 PCM bytes) and 40 coded bytes. Standard G.722.1 specifies
24/32 kbps; YKI uses the 16 kbps Siren7 profile supported by the previous
libg722_1. This implementation targets YKI, not Annex C, other bitrates,
RTP, or the entire libg722_1 API.

All processing is MoonBit: overlap/windowing, binary32 DCT-IV, region energy
estimation, differential envelope coding, category allocation, scalar/vector
quantization, Huffman coding, signs, noise fill, deterministic random state,
frame concealment, and PCM rounding. No C FFI, embedded C WASM, external
codec dependency, or host callback is used.

Public APIs: encode(Bytes), decode(Bytes), and enclosing yki-core functions
encode_g7221(Bytes), decode_g7221(Bytes). JavaScript provides
createG7221(wasm) returning synchronous encode(pcm) / decode(payload), or
Core.encodeG7221(pcm) / Core.decodeG7221(payload).

Each call resets state and preserves history across frames in that call.
Only complete frames are accepted. Limits: 64 MB PCM / 4 MB coded payload.
Invalid frames repeat the previous good spectrum once, then conceal with
silence. Raw payload is MSB first; YKI AU wrapping reverses each byte.

## Provenance and verification

This new MoonBit implementation is checked against the prior floating-point
reference implementation. It is not a clean-room implementation: interoperability
rules were examined in Steve Underwood's libg722_1, adapted from ITU reference
software. Codebooks, quantization and transform tables in tables.mbt were
transcribed from huff_tab.c, tables.c, sam2coef.h, coef2sam.h, and generated
dct4.h. The reference headers state "(C) 2004 Polycom, Inc. All rights reserved."
This rewrite does not relicense those tables or declare them public domain.
Their provenance is retained in tables.mbt.

Standard: https://www.itu.int/rec/T-REC-G.722.1

../tests/g7221/reference.json captures independently generated C reference
bitstreams and decoded PCM SHA-256 values for 100 frames each of silence,
440 Hz sine, seeded full-range noise, impulses, and alternating extrema.
Tests compare every encoded byte and the entire decoded PCM, including
overlap history and noise state. They require no C source or compiler.
Random malformed frames exercise bounded bit reads and recovery.
YKI builds, volume matching, and browser export use the enclosing project's
integration tests. No hardware verification is claimed.
