import copy
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import sys
import unittest
from jsonschema import Draft202012Validator
from yki_cli.audio import AudioEncoder, native_codec, BIT_REVERSE
from yki_cli.builder import build, led_frames
from yki_cli.format import ROOT, Image, parse
from yki_cli.ids import resolve_id


class BuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT/"yki/Ver2_U.yki").read_bytes()
        cls.schema = json.loads((ROOT/"custom-legacy/yki.schema.json").read_text())

    def build(self, overrides, **extra):
        config = {"extends":2,"overrides":overrides,**extra}
        Draft202012Validator(self.schema).validate(config)
        warnings=[]
        raw,manifest,source = build(config,ROOT,warnings.append)
        return parse(raw),manifest,warnings,raw

    def test_all_stock_files_lossless(self):
        for p in (ROOT/"yki").glob("*.yki"):
            with self.subTest(version=p.name):
                data=p.read_bytes()
                self.assertEqual(Image(data).serialize(),data)

    def test_no_override_identical_and_version_zero(self):
        _,_,_,raw=self.build([])
        self.assertEqual(raw,self.raw)
        parsed,_,_,raw=self.build([],version=0)
        self.assertEqual(parsed["inferred_version"],0)
        self.assertEqual([i for i,(a,b) in enumerate(zip(raw,self.raw)) if a!=b],[0x2e,0x372])
        golden=(ROOT/"outputs/custom_yki/Ver0_U.yki").read_bytes()
        self.assertEqual(raw,golden)

    def test_relative_yki_inheritance(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/"base.yki").write_bytes(self.raw)
            (directory/"configs").mkdir()
            result,_,_=build({"extends":"../base.yki","overrides":[]},directory/"configs",lambda _:None)
            self.assertEqual(result,self.raw)

    def test_supported_ids_and_mirror(self):
        image=Image(self.raw)
        for id_ in [655,"B655",{"medal":655},"E7BA",{"bumpsHex":"0xE7BA"},
                    ["1110","0111","1011","1010"],{"bumps":["1110","0111","1011","1010"]},"7ED5"]:
            with self.subTest(id=id_):
                self.assertEqual(resolve_id(id_,image,lambda _:None,True)["row"],655)
        result=resolve_id({"sound":117},image,lambda _:None)
        self.assertEqual(result["row"],1)
        result=resolve_id({"sound":31,"namespace":"resource","field":"songSound","medal":655},image,lambda _:None)
        self.assertEqual(result["row"],655)

    def test_uncertain_unknown_and_ambiguous_ids(self):
        image=Image(self.raw);warnings=[]
        self.assertEqual(resolve_id("F12A",image,warnings.append)["confidence"],"low")
        self.assertTrue(warnings)
        with self.assertRaisesRegex(ValueError,"confidence"):
            resolve_id("F12A",image,lambda _:None,True)
        with self.assertRaisesRegex(ValueError,"no known"):
            resolve_id("000A",image,lambda _:None)
        with self.assertRaisesRegex(ValueError,"four nibbles"):
            resolve_id("E7B",image,lambda _:None)
        with self.assertRaisesRegex(ValueError,"matches rows"):
            resolve_id({"sound":88,"field":"introSound"},image,lambda _:None)

    def test_schema_rejects_typos_and_bad_shapes(self):
        Draft202012Validator.check_schema(self.schema)
        for override in [{"id":655,"songSond":"a.mp3"},{"id":655,"led":{"frames":[[256,0,0]]}},
                         {"id":["1110","0111","1011"],"type":"song"},
                         {"id":655,"type":"normal","songSound":"a.mp3"},
                         {"id":1000},{"id":True},{"id":{"medal":655,"sound":31,"extra":True}}]:
            with self.subTest(override=override):
                self.assertTrue(list(Draft202012Validator(self.schema).iter_errors({"extends":2,"overrides":[override]})))

    def test_schema_b_prefixed_medal_and_hex_ids(self):
        image=Image(self.raw)
        validator=Draft202012Validator(self.schema)
        for value in ["B661","b661","B655","B900","0xB661",{"bumpsHex":"B661"},"B61A","E83A"]:
            with self.subTest(value=value):
                self.assertFalse(list(validator.iter_errors({"extends":7,"overrides":[{"id":value}]})))
        for value in ["B661","b661"]:
            self.assertEqual(resolve_id(value,image,lambda _:None)["row"],661)

    def test_song_led_and_audio_copy_on_write(self):
        x,m,w,raw=self.build([{"id":655,"songSound":{"builtin":107},"led":{"frames":[[255,0,0],[0,0,255]],"repeat":3}}])
        row=x["medals"][654]["pairs"];sequence=x["resources"][row[1][1]]
        self.assertEqual(sequence["pairs"][1],[0,107])
        led=x["resources"][sequence["pairs"][0][1]]
        self.assertEqual(led["frame_count"],6)
        original=Image(self.raw)
        self.assertEqual(original.assets[17]["pairs"],[[1,5],[1,31]])
        old_audio_hashes={r["asset_sha256"] for r in original.parsed["resources"] if r["kind"]=="audio"}
        self.assertEqual(old_audio_hashes,{r["asset_sha256"] for r in x["resources"] if r["kind"]=="audio"})
        self.assertTrue(w)

    def test_edit_one_alias_does_not_edit_shared_sequence(self):
        image=Image(self.raw)
        image.rows[655][1]=image.rows[654][1][:]
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/"base.yki";base.write_bytes(image.serialize())
            raw,_,_=build({"extends":"base.yki","overrides":[{"id":655,"songSound":{"builtin":107}}]},Path(tmp),lambda _:None)
            x=parse(raw)
        changed=x["resources"][x["medals"][654]["pairs"][1][1]]["pairs"][1]
        unchanged=x["resources"][x["medals"][655]["pairs"][1][1]]["pairs"][1]
        self.assertEqual(changed,[0,107])
        self.assertEqual(x["resources"][unchanged[1]]["kind"],"audio")

    def test_existing_led_repeat_keeps_one_end_marker_and_shared_asset(self):
        x,_,_,raw=self.build([{"id":655,"led":{"resource":5,"repeat":12}}])
        original=Image(self.raw)
        image=Image(raw)
        seq=image.assets[image.rows[654][1][1]]["pairs"]
        blob=image.assets[seq[0][1]]["blob"]
        old=original.assets[5]["blob"]
        self.assertEqual(blob,old[:2]+old[2:-6]*12+old[-6:])
        self.assertEqual(x["resources"][seq[0][1]]["frame_count"],1260*12)
        self.assertEqual(image.assets[5]["blob"],old)
        self.assertEqual(image.audio_blob(seq[1]),original.audio_blob(original.song_pair(original.rows[654])))
        for repeat in [0,1025,True]:
            self.assertTrue(list(Draft202012Validator(self.schema).iter_errors({"extends":2,"overrides":[{"id":655,"led":{"resource":5,"repeat":repeat}}]})))

    def test_new_song_and_normal_rows(self):
        x,m,w,_=self.build([{"id":900,"type":"song","template":655,"songSound":{"resource":31}},
                            {"id":901,"type":"normal","nameSound":{"resource":40},"summonSound":{"builtin":37},"led":{"frames":[[1,2,3]]}}])
        self.assertTrue(all(o["new"] for o in m["overrides"]))
        self.assertEqual(x["medals"][899]["pairs"][0],[65534,65534])
        normal=x["medals"][900]["pairs"]
        self.assertEqual(x["resources"][normal[0][1]]["kind"],"sequence")
        self.assertEqual(x["resources"][normal[4][1]]["kind"],"audio")
        self.assertTrue(w)
        with self.assertRaisesRegex(ValueError,"require type"):
            self.build([{"id":900,"nameSound":{"resource":40}}])
        with self.assertRaisesRegex(ValueError,"requires? songSound"):
            self.build([{"id":900,"type":"song"}])

    def test_type_conversion_and_sequential_overrides(self):
        x,_,_,_=self.build([{"id":1,"type":"song","songSound":{"resource":31}},
                            {"id":1,"introSound":None},{"id":1,"songSound":{"builtin":107}}])
        row=x["medals"][0]["pairs"]
        self.assertEqual(row[0],[65534,65534])
        self.assertEqual(row[5],[65535,65535])
        self.assertEqual(x["resources"][row[1][1]]["pairs"][1],[0,107])
        with self.assertRaisesRegex(ValueError,"only valid"):
            self.build([{"id":1,"songSound":{"resource":31}}])
        with self.assertRaisesRegex(ValueError,"type conversion requires"):
            self.build([{"id":655,"type":"normal"}])

    def test_cli_stdin_and_failed_build_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"out.yki"
            good=json.dumps({"extends":2,"version":0,"overrides":[]})
            result=subprocess.run([sys.executable,"-m","yki_cli","build","-","-o",str(target)],
                                  input=good,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            old=target.read_bytes()
            bad=json.dumps({"extends":2,"overrides":[{"id":"000A"}]})
            result=subprocess.run([sys.executable,"-m","yki_cli","build","-","-o",str(target)],
                                  input=bad,text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("no known",result.stderr)
            self.assertEqual(target.read_bytes(),old)

    def test_led_json_file_and_invalid_file_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"led.json";path.write_text(json.dumps({"frames":[[1,2,3]],"repeat":2}))
            self.assertEqual(led_frames("led.json",Path(tmp)),[[1,2,3],[1,2,3]])
            path.write_text(json.dumps({"frames":[[999,2,3]]}))
            with self.assertRaises(ValueError):led_frames("led.json",Path(tmp))

    def test_missing_audio_and_wrong_reference_kind(self):
        with self.assertRaisesRegex(ValueError,"not found"):
            self.build([{"id":655,"songSound":"absent.wav"}])
        with self.assertRaisesRegex(ValueError,"not an AU"):
            self.build([{"id":655,"songSound":{"resource":2}}])
        with self.assertRaisesRegex(ValueError,"not an RGB"):
            self.build([{"id":655,"led":{"resource":31}}])


class AudioTests(unittest.TestCase):
    def test_native_and_stock_compatible_roundtrip(self):
        image=Image((ROOT/"yki/Ver2_U.yki").read_bytes())
        blob=image.assets[31]["blob"]
        with tempfile.TemporaryDirectory() as tmp:
            encoder=AudioEncoder(tmp,lambda _:None)
            decoded=encoder.decode(blob[32:].translate(BIT_REVERSE))
        import wave
        with wave.open(str(ROOT/"outputs/yki_analysis/Ver2_U/audio/res031.wav")) as w:
            known=w.readframes(w.getnframes())
        self.assertEqual(decoded,known)

    def test_real_mp3_trim_and_extend_relocation(self):
        config={"extends":2,"overrides":[{"id":655,"type":"song","songSound":"third_party/media/yarimasunesugi.mp3"}]}
        raw,manifest,_=build(config,ROOT,lambda _:None)
        x=parse(raw);record=manifest["audio"][0]
        self.assertEqual(record["frames"],850)
        self.assertEqual(record["added_padding_samples"],0)
        self.assertEqual(record["trimmed_samples"],80)
        sequence=x["resources"][x["medals"][654]["pairs"][1][1]]
        self.assertEqual(sequence["pairs"][1][1],record["resource"])
        au=x["resources"][record["resource"]]
        self.assertEqual(au["header"]["duration_seconds"],17)
        self.assertEqual(x["inferred_version"],2)

    def test_pad_error_and_built_in_reference_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            encoder=AudioEncoder(tmp,lambda _:None)
            file=ROOT/"third_party/media/yarimasunesugi.mp3"
            with self.assertRaisesRegex(ValueError,"multiple of 320"):
                encoder.encode(file,{"frameAlignment":"error"})
            blob,record=encoder.encode(file,{"frameAlignment":"pad"})
            self.assertEqual(record["added_padding_samples"],240)
            self.assertEqual(record["frames"],851)
            with self.assertRaisesRegex(ValueError,"built-in sound"):
                encoder.encode(file,{"volume":"match"})


if __name__ == "__main__":
    unittest.main()
