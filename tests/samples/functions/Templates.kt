fun header(values: Map<String, String>): String {
    return "${values["}"]} and ${if (values.isEmpty()) "{" else "}"}"
}

fun path(dir: String): String {
    return """${dir}\""" + "\"{"
}

fun footer() {
    println("done")
}
