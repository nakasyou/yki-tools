# Generate Yo-kai Medals from Bit Patterns

Generate OpenSCAD models with the MoonBit/WASM core. Node.js handles file output and invokes OpenSCAD for STL conversion.

Build the core once before generating a medal:

```bash
pnpm --dir packages/yki-core run build
```

```bash
pnpm medal 1001 0100 1110 1010 -o outputs/3d/medal.scad
pnpm medal 1001010011101010 -o outputs/3d/medal.scad
pnpm medal '1001/0100/1110/1010' -o outputs/3d/medal.stl
```

STL conversion requires the `openscad` command. Use `--openscad /path/to/openscad` if it is installed elsewhere. When no output path is supplied, the script creates `medal_<16-bit-pattern>_<mode>.scad` in the current directory.

STL output has been verified in this environment using Nix.

There are three modes: `--mode normal` (default), `--mode classic`, and `--mode lite`.

| Mode | Geometry |
| --- | --- |
| `classic` | Traditional full model with a disc, lettering, rim, and front square features |
| `normal` | Classic model without rear lettering or front square features; retains the rim and circular recess |
| `lite` | Open frame retaining the guides, four crossbars, and curved ends |

```bash
nix shell nixpkgs#openscad -c pnpm medal \
  1011 0110 0001 1010 --mode classic -o outputs/3d/jibanyan_classic.stl
nix shell nixpkgs#openscad -c pnpm medal \
  1011 0110 0001 1010 --mode normal -o outputs/3d/jibanyan_normal.stl
```

## Fit Adjustments

Both normal and classic models have 0.2 mm removed from the bottom, equivalent to one print layer, giving a total height of 3.8 mm. Each guide is thinned by 0.2 mm on its inner face, widening the gap to 19.4 mm. The crossbars around the lettering share these inner face positions.

The central base on the side without pegs is also thinned. Where the front recess is removed, its thickness is 1.3 mm. Classic retains the disc, lettering, rim, and front recesses; normal removes only the lettering and square features.

```bash
nix shell nixpkgs#openscad -c pnpm medal 1001 0100 1110 1010 -o outputs/3d/medal.stl
```

## Lite Mode

`--lite` removes the rear lettering and its surrounding frame, including the outer arcs and crossbars above and below the lettering. It also removes the front square recesses and steps, leaving a flat surface. The base outside the guides is cut away, giving a total width of 22 mm.

The reading pegs retain the same XY positions, tip shapes, and bit orientation as normal and classic. On the peg side, a 2.4 mm wide crossbar is retained beneath each of the four rows, with openings cut through the base between rows. Crossbars remain connected even at zero bits and support the guides and pegs on both sides.

The side without pegs has a large opening, retaining only a 3 mm wide end crossbar. Both ends retain the original curved edges of the 43 mm diameter disc.

Before bottom trimming, the crossbars on the reading side are 2 mm thick at the center and 2.5 mm near the guides; the end crossbar is 1.5 mm thick. Removing 0.2 mm from the bottom corresponds to one layer of the original 4 mm model printed in 20 layers at 0.2 mm per layer. The resulting thicknesses are 1.8 mm at the center, 2.3 mm near the guides, and 1.3 mm at the end, with a maximum height of 3.8 mm. Peg tip shapes and protrusion above the base are preserved.

The guide outer faces remain at X = ±11 mm. Thinning each inner face by 0.2 mm places the inner faces at X = ±9.7 mm, giving 1.3 mm thick guides and a 19.4 mm gap. Bottom trimming also reduces guide height to 3.8 mm. The end notches are retained.

The template parameters are `liteBaseHeight` for the original end crossbar thickness, `liteRowWidth` for the four crossbar widths, `baseReduction` for bottom trimming, and `guideInset` for thinning the inner guide faces. The last two parameters also apply to normal and classic. Default output filenames for lite mode include `_lite`.

```bash
nix shell nixpkgs#openscad -c pnpm medal \
  1011 0110 0001 1010 --lite -o outputs/3d/jibanyan_lite.stl
```

When editing the template directly in OpenSCAD, select `mode = "normal";`, `"classic"`, or `"lite"`.

## Bit Orientation

Input consists of four rows from top to bottom. `1` means a peg is present; `0` means absent. The default input orientation is the lookup table's canonical orientation, ending in `1010`. Each row is reversed horizontally to match the classical model.

For example, Jibanyan's input `1011 0110 0001 1010` becomes `1101 0110 1000 0101` in model coordinates. The original Keukegen Kai pattern `1111 1010 0001 0101` likewise matches the table pattern `1111 0101 1000 1010`.

Use `--orientation physical` to disable automatic reversal when specifying bits as viewed from the model's peg side. `--mirror` applies an additional horizontal reversal after this conversion. The generator does not validate terminal bits or infer orientation from them.

## Model Provenance

The base model comes from `Classical Yo-kai Medal - 1615579.zip`. Its original dimensions are a 43 mm diameter, 2 mm base thickness, 2.5 mm track height, and 4 mm maximum height. The adjustments above modify its thickness and guides. The four peg rows are centered, with the first input row at Y = 18 mm and the fourth at Y = 0 mm. Converted bits are assigned to the original `code1` through `code4` definitions in order.

The original description specifies compatibility with DX Yo-kai Watch Model Zero and excludes the original DX Yo-kai Watch. Fit and recognition on Watch U have not been tested on hardware.

Source: [Classical Yo-kai Medal](https://www.thingiverse.com/thing:1615579) by paulliu. The modified template is kept separately at `templates/classical-yo-kai-medal.scad`. Downloaded archives and extracted reference materials are stored in `third_party/models/` and excluded from Git. The downloaded ZIP identifies the original model's license as Creative Commons Public Domain Dedication.

The earlier English model at `third_party/models/YokaiWatchMedal.scad` is retained for reference and is not used for generation.

## MoonBit API

`core.generateMedal(bits, { mode, orientation, mirror })` returns `{ source, rows, mode, filename }` without filesystem or process capabilities. The same API runs in Node and browsers. The OpenSCAD template is embedded in WASM at build time by `packages/yki-core/scripts/medal-template.mjs`; edit the attributed template and rebuild to update the geometry.

The separate `portrait_relief/` image/depth experiments still use Python and their existing dependencies.
