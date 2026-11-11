pub(crate) fn r#match(input: &str) -> bool {
    !input.is_empty()
}

pub(in crate::parse) fn r#type() -> &'static str {
    "type"
}
