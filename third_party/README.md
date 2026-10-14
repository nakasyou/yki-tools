# Third-Party Works and Materials

Local scripts and third-party works are kept separate by provenance. The following local files are excluded by `.gitignore` and are not included in distribution:

- `../yki/`: Original Yo-kai Watch U update files.
- `archives/`: Downloaded ZIP archives containing original files or media.
- `models/`: Downloaded models, ZIP archives, extracted reference models, and PDFs.
- `media/`: Input audio, videos, images, lyrics, and separated audio stems. This includes files whose sources or usage terms have not been verified; they are not published.
- `local/work/`: Downloaded repositories, web pages, images, recovered data, and local decoder work files.

## Published Template Attribution

`../packages/3d/templates/classical-yo-kai-medal.scad` is a modified version of paulliu's [Classical Yo-kai Medal](https://www.thingiverse.com/thing:1615579). The downloaded ZIP's `LICENSE.txt` states Creative Commons Public Domain Dedication. The modifications add normal/classic/lite mode selection and base and guide thickness adjustments to the original code definitions and geometry. This is a modified template, not the unmodified original file.

`models/YokaiWatchMedal.scad` is a reference model from Herrigold's [Yokai Watch Medal Builder](https://www.thingiverse.com/thing:2509265). Its existing header states Creative Commons Attribution. It is not used for generation and is excluded as a local reference.

Downloaded codec sources remain subject to their respective licenses. They are managed separately from the locally created wrapper `../custom-legacy/native/codec.c`.

## MoonBit codec tables

The YKI codec processing now lives in packages/yki-core/g7221 as MoonBit.
Its tables.mbt contains transcribed codebooks, quantization and transform tables
from the local libg722_1 / ITU reference implementation, with the original
Polycom notice retained. These embedded tables are an exception to the general
exclusion of downloaded source trees. See
[codec provenance](../packages/yki-core/g7221/README.md).
The C source tree is used only for optional reference testing and the legacy
Python CLI, not for building or running the MoonBit CLI, SDK, or web editor.
