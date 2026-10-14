///|
pub fn request(value : Json) -> Json raise ThreeDError {
  match text(get(value, "op")) {
    "generate_medal" =>
      generate_medal(
        text(get(value, "bits")),
        mode=str_default(value, "mode", "normal"),
        orientation=str_default(value, "orientation", "canonical"),
        mirror=if has(value, "mirror") {
          match get(value, "mirror") {
            True => true
            False => false
            _ => raise ThreeDError("mirror must be a boolean")
          }
        } else {
          false
        },
      )
    _ => raise ThreeDError("unknown operation")
  }
}
