extension ByteBuffer {
    // A generic parameter list and a parameter list, one per line, longer than 30 lines together.
    @discardableResult
    public mutating func setMultipleIntegers<
        T1: FixedWidthInteger,
        T2: FixedWidthInteger,
        T3: FixedWidthInteger,
        T4: FixedWidthInteger,
        T5: FixedWidthInteger,
        T6: FixedWidthInteger,
        T7: FixedWidthInteger,
        T8: FixedWidthInteger,
        T9: FixedWidthInteger,
        T10: FixedWidthInteger,
        T11: FixedWidthInteger,
        T12: FixedWidthInteger,
        T13: FixedWidthInteger,
        T14: FixedWidthInteger,
        T15: FixedWidthInteger,
        T16: FixedWidthInteger
    >(
        _ value1: T1,
        _ value2: T2,
        _ value3: T3,
        _ value4: T4,
        _ value5: T5,
        _ value6: T6,
        _ value7: T7,
        _ value8: T8,
        _ value9: T9,
        _ value10: T10,
        _ value11: T11,
        _ value12: T12,
        _ value13: T13,
        _ value14: T14,
        _ value15: T15,
        _ value16: T16,
        at index: Int
    ) -> Int {
        index
    }

    public func after() -> Int {
        0
    }
}
