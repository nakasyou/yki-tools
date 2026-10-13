import copy
import json
from pathlib import Path
import struct
import tempfile
from .audio import AudioEncoder
from .format import Image, ROOT, FIELDS, EMPTY, parse
from .ids import resolve_id


def load_base(config, directory):
    value = config["extends"]
    path = ROOT/"yki"/f"Ver{value}_U.yki" if isinstance(value,int) else directory/value
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"base YKI not found: {path}")
    return path, Image(path.read_bytes())


def led_frames(value, directory):
    if isinstance(value,str):
        path = directory/value
        if not path.is_file():
            raise ValueError(f"LED file not found: {path}")
        value = json.loads(path.read_text())
    if isinstance(value,list):
        value = {"frames":value}
    if not isinstance(value,dict) or set(value)-{"frames","repeat"} or "frames" not in value:
        raise ValueError("LED JSON must be {frames: [[r,g,b], ...], repeat: integer}")
    frames = value["frames"]
    repeat = value.get("repeat",1)
    if not isinstance(frames,list) or not frames or not isinstance(repeat,int) or isinstance(repeat,bool) or not 1<=repeat<=1024:
        raise ValueError("LED frames must be nonempty and repeat must be 1..1024")
    if len(frames)*repeat > 1000000:
        raise ValueError("LED expansion exceeds one million frames")
    for f in frames:
        if not isinstance(f,list) or len(f)!=3 or any(type(v) is not int or not 0<=v<=255 for v in f):
            raise ValueError("every LED frame must have three integer channels in 0..255")
    return frames*repeat


def make_led(image, value, directory, warn):
    if isinstance(value,dict) and "resource" in value:
        index = value["resource"]
        if index >= len(image.assets) or image.assets[index]["kind"] != "led_candidate":
            raise ValueError(f"LED resource {index} is not an RGB-like asset")
        repeat = value.get("repeat",1)
        if type(repeat) is not int or not 1 <= repeat <= 1024:
            raise ValueError("LED repeat must be 1..1024")
        if repeat == 1:
            return [1,index]
        blob = image.assets[index]["blob"]
        if len(blob)<14 or (len(blob)-8)%6 or blob[:2]!=b'\xff\xff' or blob[-6:]!=b'\xff'*6:
            raise ValueError("LED resource cannot be repeated: unsupported frame layout")
        words = struct.unpack(f"<{len(blob)//2}H",blob)
        if any(v>255 for v in words[1:-3]):
            raise ValueError("LED resource cannot be repeated: invalid channel values")
        count = (len(blob)-8)//6
        if count*repeat>1000000:
            raise ValueError("LED expansion exceeds one million frames")
        warn(f"LED resource {index}: repeating {count} frames {repeat} times; tick period and hardware behavior remain unverified")
        # Repeat frames, excluding the end marker between repetitions.
        return image.append("led_candidate",blob[:2]+blob[2:-6]*repeat+blob[-6:])
    frames = [[0,0,0]] if value is None else led_frames(value,directory)
    warn("custom LED uses three raw channel values per frame; RGB physical order and tick period remain unverified")
    words = [0xFFFF] + [v for f in frames for v in f] + [0xFFFF]*3
    return image.append("led_candidate",struct.pack(f"<{len(words)}H",*words))


def media_file(value, directory):
    return directory/(value if isinstance(value,str) else value["file"])


def build(config, directory, warn, strict=False):
    source, image = load_base(config,directory)
    resolutions = []
    changes = []
    strict = strict or config.get("mappingPolicy","warn") == "strict"
    if "version" in config:
        version = config["version"]
        image.root[11] = [0,0x40+version]
        if version not in (0,2,3,4,5,6,7):
            warn(f"version {version} selects a stock-listed built-in ID but its spoken output has not been verified")
    with tempfile.TemporaryDirectory(prefix="yki-cli-") as temporary:
        encoder = AudioEncoder(temporary,warn)

        def sound(value, old_pair):
            if value is None:
                return EMPTY[:]
            if isinstance(value,dict) and "builtin" in value:
                return [0,value["builtin"]]
            if isinstance(value,dict) and "resource" in value:
                i = value["resource"]
                if i >= len(image.assets) or image.assets[i]["kind"] != "audio":
                    raise ValueError(f"sound resource {i} is not an AU asset")
                return [1,i]
            options = dict(config.get("audio",{}))
            if isinstance(value,dict):
                options.update({k:v for k,v in value.items() if k != "file"})
            ref = image.audio_blob(old_pair)
            if "referenceResource" in options:
                i = options["referenceResource"]
                if i >= len(image.assets) or image.assets[i]["kind"] != "audio":
                    raise ValueError(f"referenceResource {i} is not an AU asset")
                ref = image.assets[i]["blob"]
            blob, record = encoder.encode(media_file(value,directory),options,ref)
            pair = image.append("audio",blob)
            record["asset_handle"] = pair[1]
            return pair

        for index, override in enumerate(config["overrides"]):
            resolved = resolve_id(override["id"],image,warn,strict)
            resolutions.append(resolved)
            number = resolved["row"]
            previous = copy.deepcopy(image.rows[number-1])
            is_new = not image.active(previous)
            requested_type = override.get("type",image.row_type(previous))
            converting = requested_type != image.row_type(previous)
            if is_new and "type" not in override:
                raise ValueError(f"B{number}: new medal rows require type: normal or song")
            if "template" in override:
                template = resolve_id(override["template"],image,warn,strict)["row"]
                row = copy.deepcopy(image.rows[template-1])
                if not image.active(row):
                    raise ValueError(f"B{template} is not an active template")
                if "type" not in override:
                    requested_type = image.row_type(row)
                elif image.row_type(row) != requested_type:
                    raise ValueError("template type does not match override.type")
            elif is_new or requested_type != image.row_type(previous):
                template = 655 if requested_type == "song" else 1
                row = copy.deepcopy(image.parsed["medals"][template-1]["pairs"])
                if requested_type == "song" and image.kind(row[1]) != "sequence":
                    raise ValueError("base has no known B655 song template; provide an explicit template")
                row[4] = EMPTY[:]
                row[6] = EMPTY[:]
                row[8] = EMPTY[:]
            else:
                row = copy.deepcopy(previous)
            if converting and "template" not in override:
                required = "songSound" if requested_type == "song" else "nameSound"
                if override.get(required) is None:
                    raise ValueError(f"B{number}: type conversion requires {required} or an explicit template")
            if is_new:
                required = "songSound" if requested_type == "song" else "nameSound"
                if override.get(required) is None:
                    raise ValueError(f"B{number}: new {requested_type} medals require {required}")
                warn(f"new B{number} row initialized; physical bump recognition still depends on the watch's existing conversion")
            if requested_type == "normal" and "songSound" in override:
                raise ValueError("songSound is only valid for type: song")
            for field, slot in FIELDS.items():
                if field not in override:
                    continue
                old = row[slot]
                replacement = sound(override[field],image.audio_pair(old))
                if image.kind(old) == "sequence" and replacement != EMPTY:
                    led = image.assets[old[1]]["pairs"][0][:]
                    row[slot] = image.append("sequence",pairs=[led,replacement])
                else:
                    row[slot] = replacement
            if requested_type == "song" and ("songSound" in override or "led" in override):
                old = row[1]
                if image.kind(old) != "sequence":
                    raise ValueError("song override needs an existing song template")
                led, old_audio = image.assets[old[1]]["pairs"]
                new_audio = sound(override["songSound"],old_audio) if "songSound" in override else old_audio[:]
                if new_audio == EMPTY:
                    if "led" in override:
                        raise ValueError("cannot attach LED data to a null songSound")
                    row[1] = EMPTY[:]
                else:
                    new_led = make_led(image,override["led"],directory,warn) if "led" in override else led[:]
                    row[1] = image.append("sequence",pairs=[new_led,new_audio])
            elif requested_type == "normal" and "led" in override:
                if override["led"] is None:
                    row[0] = image.audio_pair(row[0])
                else:
                    audio = image.audio_pair(row[0])
                    if audio[0] not in (0,1):
                        raise ValueError("normal medal LED needs summonSound or a template with a summon reference")
                    row[0] = image.append("sequence",pairs=[make_led(image,override["led"],directory,warn),audio])
            image.rows[number-1] = row
            changes.append(dict(override_index=index,medal_row=number,type=requested_type,
                                new=is_new,previous_pairs=previous,edited_pairs_stable_handles=row))
        data = image.serialize()
        parsed = parse(data)
        for change in changes:
            change["output_pairs"] = parsed["medals"][change["medal_row"]-1]["pairs"]
        for record in encoder.records:
            record["resource"] = image.last_mapping[record["asset_handle"]]
            blob = image.assets[record["asset_handle"]]["blob"]
            resource = parsed["resources"][record["resource"]]
            extracted = data[resource["offset"]:resource["offset"]+resource["asset_bytes"]]
            if extracted != blob:
                raise ValueError("saved AU differs from encoded AU")
        manifest = dict(source=str(source),source_sha256=image.parsed["sha256"],
                        output_sha256=parsed["sha256"],size=len(data),
                        version_spoken_id=parsed["version_related_builtin"],
                        version=parsed["inferred_version"],version_semantics="spoken version selection; firmware compatibility identity is not proven",
                        resolutions=resolutions,overrides=changes,audio=encoder.records,
                        resource_count=parsed["header"]["resource_count"],
                        handle_to_output_resource=image.last_mapping,validation=parsed["validation"],
                        hardware_tested=False,
                        notes=["Existing assets are retained; edited references use copy-on-write.",
                               "LED stops after audio on the tested shortened B655 song; other playback paths unverified."])
    return data,manifest,source
