///|
test "embedded data contains valid JSON objects" {
  assert_true(@json.parse(schema_json) is Object(_))
  assert_true(@json.parse(bump_lookup_json) is Object(_))
  assert_true(@json.parse(bump_evidence_json) is Object(_))
}
