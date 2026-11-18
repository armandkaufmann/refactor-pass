package paths

func sep() string {
	return `\`
}

func both() (string, string) {
	return `\\`, `{"a": 1} // \
}\`
}

func escaped() (string, rune, rune) {
	return "a\"{", '\'', '\\'
}

func last() {}
