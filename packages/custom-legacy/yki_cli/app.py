import argparse
import json
import math
from pathlib import Path
import sys
import struct
import tempfile
from jsonschema import Draft202012Validator
from .builder import build, load_base, media_file, led_frames
from .format import ROOT, parse, FIELDS
from .ids import resolve_id

SCHEMA = ROOT / "packages/custom-legacy/yki.schema.json"


def read_config(path, text=None):
    config = json.loads(path.read_text() if text is None else text)
    validator = Draft202012Validator(json.loads(SCHEMA.read_text()))
    errors = sorted(validator.iter_errors(config),key=lambda e:str(list(e.path)))
    if errors:
        error = errors[0]
        location = ".".join(map(str,error.path)) or "$"
        raise ValueError(f"JSON schema: {location}: {error.message}")
    return config


def finite_json(value):
    if isinstance(value,float) and not math.isfinite(value):
        return None
    if isinstance(value,dict):
        return {k:finite_json(v) for k,v in value.items()}
    if isinstance(value,list):
        return [finite_json(v) for v in value]
    return value


def atomic_write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        temp = Path(f.name)
        try:
            f.write(data)
            f.flush()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description="JSONから妖怪ウォッチUのykiを生成")
    commands = ap.add_subparsers(dest="command",required=True)
    b = commands.add_parser("build",help="JSONを読み、音声をエンコードしてykiを生成")
    b.add_argument("config",type=Path)
    b.add_argument("-o","--output",type=Path)
    b.add_argument("--strict-mapping",action="store_true")
    b.add_argument("--base-dir",type=Path,help="相対パスの基準（通常はJSONのあるフォルダー、標準入力では現在のフォルダー）")
    v = commands.add_parser("validate",help="JSONスキーマ、基底yki、ID、入力ファイルを検査（エンコードはしない）")
    v.add_argument("config",type=Path)
    v.add_argument("--strict-mapping",action="store_true")
    v.add_argument("--base-dir",type=Path)
    i = commands.add_parser("inspect",help="ykiの数量・バージョン読み上げ値を表示")
    i.add_argument("file",type=Path)
    commands.add_parser("schema",help="JSON Schemaを標準出力へ表示")
    args = ap.parse_args()
    warnings = []

    def warn(text):
        warnings.append(text)
        print(f"warning: {text}",file=sys.stderr)

    try:
        if args.command == "schema":
            print(SCHEMA.read_text(),end="")
            return
        if args.command == "inspect":
            import collections
            x = parse(args.file.read_bytes())
            print(json.dumps(dict(file=str(args.file.resolve()),size=x["size"],sha256=x["sha256"],
                    version=x["inferred_version"],version_spoken_id=x["version_related_builtin"],
                    resources=dict(collections.Counter(r["kind"] for r in x["resources"])),
                    active_name_rows=sum(m["pairs"][4][0] in (0,1) for m in x["medals"]),
                    validation=x["validation"]),indent=2))
            return
        stdin = str(args.config) == "-"
        path = Path.cwd()/"stdin.json" if stdin else args.config.resolve()
        directory = args.base_dir.resolve() if args.base_dir else path.parent
        config = read_config(path,sys.stdin.read() if stdin else None)
        if args.command == "validate":
            source,image = load_base(config,directory)
            strict = args.strict_mapping or config.get("mappingPolicy") == "strict"
            ids = []
            for o in config["overrides"]:
                ids.append(resolve_id(o["id"],image,warn,strict))
                if "template" in o:
                    resolve_id(o["template"],image,warn,strict)
                for field in list(FIELDS)+["songSound"]:
                    value = o.get(field)
                    if isinstance(value,str) or isinstance(value,dict) and "file" in value:
                        if not media_file(value,directory).is_file():
                            raise ValueError(f"audio file not found: {media_file(value,directory)}")
                if "led" in o and o["led"] is not None and not (isinstance(o["led"],dict) and "resource" in o["led"]):
                    led_frames(o["led"],directory)
            print(json.dumps(dict(schema_valid=True,base=str(source),resolutions=ids,
                                  warnings=warnings,encoded=False),ensure_ascii=False,indent=2))
            return
        if stdin and not args.output and "output" not in config:
            raise ValueError("standard input requires --output or the JSON output field")
        output = args.output.resolve() if args.output else (directory/config["output"]).resolve() if "output" in config else path.with_suffix(".yki")
        if output.suffix.lower() != ".yki":
            raise ValueError("output must have the .yki extension")
        source,_ = load_base(config,directory)
        manifest_path = output.with_suffix(".manifest.json")
        if output == source or output == path or manifest_path == path or manifest_path == source:
            raise ValueError("output must not overwrite the input YKI or JSON config")
        print("Building YKI; audio conversion may take a few seconds per sound…",file=sys.stderr)
        data,manifest,source = build(config,directory,warn,args.strict_mapping)
        manifest.update(output=str(output),config="<stdin>" if stdin else str(path),path_base=str(directory),warnings=warnings)
        manifest_bytes = (json.dumps(finite_json(manifest),ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode()
        atomic_write(output,data)
        atomic_write(manifest_path,manifest_bytes)
        print(output)
        print(f"manifest: {manifest_path}")
    except (ValueError,OSError,KeyError,IndexError,struct.error) as exc:
        ap.exit(1,f"error: {exc}\n")
