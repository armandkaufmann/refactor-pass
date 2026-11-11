package shop

class Orders(private val repo: Repo) {
    suspend fun load(
        id: String,
        limit: Int = 10,
    ): Result<Order> {
        return repo.find(id, limit)
    }

    fun count(): Int = repo.size

    fun <T> first(items: List<T>): T? {
        return items.firstOrNull()
    }

    private fun String.clean(): String {
        return trim()
    }
}

fun main() {
    val greet = { name: String -> "Hi $name" }
    println(greet("you"))
}

interface Repo {
    fun find(id: String, limit: Int): Result<Order>
    val size: Int
}
