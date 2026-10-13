# YKI CLI

This CLI inherits an existing YKI file and overrides medals, audio, and LEDs using a JSON configuration. It uses this repository's analysis results, original files, and the G.722.1 reference implementation. It is not a standalone distribution package.

## Running the CLI

Requirements: uv, Python 3.13 or later, ffmpeg, and a C compiler (`cc`). Run the following commands from the repository root. The native codec is compiled automatically on the first audio operation.

```sh
uv run --project custom-legacy yki-cli validate custom-legacy/examples/mogumogu.json
uv run --project custom-legacy yki-cli build custom-legacy/examples/mogumogu.json -o outputs/custom_yki/Ver2_U_cli_mogumogu.yki
uv run --project custom-legacy yki-cli inspect outputs/custom_yki/Ver2_U_cli_mogumogu.yki
uv run --project custom-legacy yki-cli schema
```

`build` creates a YKI file and an adjacent `.manifest.json`. The manifest records ID evidence and confidence, measured audio properties, reference relocation, and warnings. `validate` checks the schema, base file, IDs, and input files. Audio encoding and final binary validation are performed by `build`.

Standard input is also supported:

```sh
uv run --project custom-legacy yki-cli build - --base-dir custom-legacy/examples -o outputs/custom_yki/stdin.yki < custom-legacy/examples/mogumogu.json
```

## JSON Configuration

```json
{
  "$schema": "../yki.schema.json",
  "extends": 2,
  "version": 2,
  "mappingPolicy": "strict",
  "audio": { "frameAlignment": "trim", "volume": "match", "allowClipping": true },
  "overrides": [
    { "id": "0xE7BA", "type": "song", "songSound": "../../third_party/media/yarimasunesugi.mp3" }
  ]
}
```

`extends` accepts an original version number from 2 through 7 or a path such as `"../xxx.yki"`. Relative paths are resolved from the JSON file's directory; `--base-dir` changes that base. For standard input, the default base is the current directory. The `output` field can also specify the destination, but `-o` takes precedence.

`overrides` are applied in order. Later entries for the same medal inherit earlier changes. Unspecified fields are inherited. Shared audio and sequences are copied before modification so changes do not affect other medals. Original resources are retained, so file size may increase.

`version` sets the spoken version value from 0 through 10. Changing Ver.2 to 0 has been verified on hardware. Values 1 and 8 through 10 produce warnings because they are unverified. This field has not been confirmed to control the device's internal update eligibility checks.

## IDs

The same `id` field accepts the following forms:

| Example                                                                     | Meaning                                                            |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `655` / `"B655"` / `{"medal":655}`                                          | B number in the medal table                                        |
| `"0xE7BA"` / `{"bumpsHex":"E7BA"}`                                          | Four peg rows in hexadecimal, including the terminal row           |
| `["1110","0111","1011","1010"]` / `{"bumps":["1110","0111","1011","1010"]}` | Four rows in insertion order; 1 means a raised peg                 |
| `{"sound":117,"namespace":"builtin","field":"nameSound"}`                   | Find the medal referencing that internal sound ID                  |
| `{"sound":31,"namespace":"resource","field":"songSound","medal":655}`       | Find by local audio resource and narrow the result by medal number |

Terminal rows `1010` and mirrored `0101` are supported. Three-digit peg patterns are rejected because they omit the terminal row. Sound IDs and medal IDs use different namespaces. If several medals match, the CLI reports the candidates and fails; use `medal` to disambiguate.

The peg-pattern-to-B-number mapping is not fully understood. E7B → B655, verified against the printed B number, has high confidence. Other observed mappings have medium confidence, and formula-based mappings have low confidence. Medium- and low-confidence mappings normally produce warnings; `mappingPolicy: "strict"` or `--strict-mapping` rejects them. Unknown mappings always fail. B numbers and existing sound references can be resolved directly.

## Medal Types and New Entries

`type` is either `"normal"` or `"song"`. Existing medals can omit it to inherit their type. New medals require a type and a primary sound.

| Field         | Slot / target                                                         |
| ------------- | --------------------------------------------------------------------- |
| `summonSound` | Normal medal p0                                                       |
| `tribeSound`  | p2                                                                    |
| `nameSound`   | Normal medal p4; primary sound for a new normal medal                 |
| `introSound`  | p5                                                                    |
| `postSound`   | p6                                                                    |
| `callSound`   | p8                                                                    |
| `songSound`   | Within a song medal's p1 sequence; primary sound for a new song medal |

The slot structure has been analyzed, but some role names for normal medals remain inferred. Song medals have a dedicated LED and song sequence, with a different audio layout from normal medals. `songSound` cannot be used with `normal`.

Use a field such as `template: 655` to copy all slots from another medal. An explicitly specified type must match the template's type. Changing types requires a primary sound or an explicit template.

See `examples/new-medal.json` for a new entry. Unused rows from B1 through B988 can be registered. Creating a row is supported, but whether the device recognizes that B number from physical pegs requires separate hardware testing. The CLI does not generate unknown peg mappings or device recognition logic.

## Audio

Each `xxxSound` accepts the following forms:

```json
{
  "songSound": "./song.mp3",
  "introSound": { "file": "./intro.wav", "volume": "preserve", "frameAlignment": "trim" },
  "callSound": { "builtin": 107 },
  "postSound": { "resource": 40 }
}
```

`null` clears the slot. `resource` is an AU audio resource number in the inherited file. Resource numbers are relocated in the output; consult the generated manifest for their final numbers.

Audio files are converted to mono, 16 kHz, 16 kbps AU audio, with each 20 ms frame containing 320 samples and 40 compressed bytes. This is distinct from the standard `.au` container. Files require 4096-byte alignment, which is separate from padding audio with silence.

On 2026-10-12, the user reported successful hardware playback of 242.20 seconds (4 minutes 2.20 seconds). The longest original recording, 47.56 seconds, is not the playback limit. At least 242.20 seconds can play under the reported conditions, but the maximum duration is unknown. The file and audio slot were not supplied, so the report is not tied to validation of a specific CLI output. See `../research/reports/2026-10-12_long_audio_playback.txt`. The current CLI limits converted PCM to 64,000,000 bytes, or at most 2,000 seconds; this is a CLI limit, separate from device limits.

Set global defaults with `audio` and override them per input using a `file` object.

| Option                             | Behavior                                                             |
| ---------------------------------- | -------------------------------------------------------------------- |
| `frameAlignment: "trim"` (default) | Discard a partial frame of at most 19.9375 ms without adding silence |
| `"pad"`                            | Add the minimum silence needed to reach a multiple of 20 ms          |
| `"error"`                          | Fail if a partial frame remains                                      |
| `volume: "preserve"` (default)     | Preserve input gain                                                  |
| `"peak"`                           | Match the original audio's sample peak                               |
| `"match"`                          | Bring measured encoded LUFS closer to the original audio             |
| `referenceResource`                | Explicitly select the AU resource used for comparison                |
| `allowClipping: true`              | Allow PCM saturation during volume matching; default is false        |

`peak` and `match` normally reference the local audio being replaced. Built-in device sounds have no available waveform, so specify `referenceResource` when needed. Unreachable volume targets produce warnings and measured results are recorded. The original song contains clipping, so the Mogumogu example explicitly permits saturation. This introduces distortion.

## LEDs

```json
{
  "id": 655,
  "led": {
    "frames": [
      [255, 0, 0],
      [0, 255, 0],
      [0, 0, 255]
    ],
    "repeat": 100
  }
}
```

Each frame has three channels with values from 0 through 255. `led: "./led.json"` loads either the same object or a frame array from an external file. `{"resource":5}` references an existing LED resource. `null` replaces a song medal's LED with one black frame, or clears a normal medal's LED sequence.

For song medals, LEDs apply to the song sequence; for normal medals, they apply to the p0 summon sequence. Physical RGB order and frame period remain unknown, so there is no fps setting or automatic time-based scaling. In the shortened Mogumogu experiment, hardware testing confirmed that LEDs stopped when the audio ended even with the original LED sequence retained. Newly generated LED patterns and added sequences for normal medals require hardware testing.

## LEDs for Longer Audio

Replacing audio alone does not change the number of LED frames. Use `repeat` to extend an existing LED resource:

```json
"led": {"resource": 11, "repeat": 12}
```

`resource: 11` is the LED resource used by B655 in the original Ver7 file; Ver2 uses resource 5. Repeating 1,260 frames 12 times produces 15,120 frames. Only the frame data is repeated, without intermediate termination markers. The shared original resource remains intact and a separate extended resource is created. The limits are 1,024 repetitions and one million expanded frames.

B655's original audio lasts 24.56 seconds, so 12 repetitions provide a margin for a 242.20-second trial. The actual LED period and extended sequence's hardware behavior are unverified; this setting does not guarantee 294.72 seconds. A previous shortening experiment confirmed that LEDs stop when audio ends if the audio is shorter than the LED sequence.

## Validation

```sh
uv run --project custom-legacy python -m unittest discover -s custom-legacy/tests -v
```

Tests cover byte-for-byte unchanged rebuilds of all six original versions, Ver.0 reproduction, ID confidence handling, shared-reference protection, new medals, LEDs, actual MP3 conversion, standard input, and preservation of existing output on failure. Generation also re-analyzes pointers, checksums, and AU lengths. The CLI's generated files themselves have not been verified on hardware.
