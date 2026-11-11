import Foundation

protocol Loader {
    func load(id: Int) async throws -> Order
}

final class Store {
    private var cache: [Int: Order] = [:]

    init(cache: [Int: Order] = [:]) {
        self.cache = cache
    }

    deinit {
        cache.removeAll()
    }

    @MainActor
    func longOne(
        a: Int,
        b: String = "x"
    ) async throws -> Int {
        return a
    }

    subscript(id: Int) -> Order? {
        return cache[id]
    }

    static func make() -> Store {
        Store()
    }
}
