struct Version: Comparable {
    let major: Int

    static func < (lhs: Version, rhs: Version) -> Bool {
        lhs.major < rhs.major
    }

    static func == (lhs: Version, rhs: Version) -> Bool {
        lhs.major == rhs.major
    }

    var pattern: String {
        #"a "quoted" {brace"#
    }

#if os(iOS)
    func platform() -> String {
        "iOS"
    }
#else
    func platform() -> String {
        "other"
    }
#endif
}

protocol Loader {
    func load(id: Int) async throws -> Version
    var name: String { get }
}

struct Calculator {
    func `adds two numbers`() -> Int {
        1 + 1
    }
}
