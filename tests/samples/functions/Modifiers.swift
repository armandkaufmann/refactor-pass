public struct Request {
    let path: String

    package init(path: String) {
        self.path = path
    }

    package func digestHex() -> String {
        path
    }

    public consuming func withReader<R>(_ body: (String) -> R) -> R {
        body(path)
    }

    borrowing func peek() -> Int {
        path.count
    }

    static prefix func - (request: Request) -> Request {
        request
    }

    func describe(_ d: [String: String]) -> String {
        return "{\(d.keys.joined(separator: "}"))}"
    }

    func after() -> Int {
        1
    }
}
