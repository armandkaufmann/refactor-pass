fn escape() -> &'static str {
    r"\"
}

fn json() -> &'static str {
    r#"{"error": "["}"#
}

fn multi() -> String {
    let s = "first {
second }";
    s.to_string()
}

fn chars() -> (char, u8) {
    ('\u{1F600}', b'\'')
}

fn after() {}
