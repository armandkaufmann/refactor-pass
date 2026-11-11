package shop

fun interface Dns {
  fun lookup(host: String): List<String>
}

interface Observer {
  fun onHeaders(
    streamId: Int,
    last: Boolean,
  ): Boolean

  fun onData(streamId: Int): Boolean
}

class Cache {
  private fun response(addresses: List<String>) =
    Message(
      answers = addresses,
    )

  fun <T : Any> get(key: String): T? = map[key] as T?

  fun spec() = """return "hey" (""""

  fun after() {
    return
  }
}
