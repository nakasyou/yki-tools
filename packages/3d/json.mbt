///|
pub suberror ThreeDError {
  ThreeDError(String)
}

///|
fn require(condition : Bool, message : String) -> Unit raise ThreeDError {
  if !condition {
    raise ThreeDError(message)
  }
}

///|
fn text(j : Json) -> String raise ThreeDError {
  match j {
    String(s) => s
    _ => raise ThreeDError("expected string")
  }
}

///|
fn get(j : Json, key : String) -> Json {
  match j {
    Object(m) => m.get(key).unwrap_or(Json::null())
    _ => Json::null()
  }
}

///|
fn has(j : Json, key : String) -> Bool {
  match j {
    Object(m) => m.contains(key)
    _ => false
  }
}

///|
fn str_default(
  j : Json,
  key : String,
  fallback : String,
) -> String raise ThreeDError {
  if has(j, key) {
    text(get(j, key))
  } else {
    fallback
  }
}
