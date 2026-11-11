package samples

class ClientTest {
    @Test fun getsTheBody() {
        assertEquals("ok", get())
    }

    @Test
    fun `returns 404 (not found) for a missing path`() {
        assertEquals(404, status("/missing"))
    }

    @JvmName("bodyOf") @JvmStatic fun body(response: Response): String {
        return response.body
    }
}

internal actual fun <T> Collection<T>.toImmutableSet(): Set<T> =
    toSet()
