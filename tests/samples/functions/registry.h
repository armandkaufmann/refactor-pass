#pragma once
#define WARNINGS_POP_()

namespace store {

enum class level { off, on };
namespace names { using level_enum = level; }

template <typename Key, class Compare>
class SkipList {
public:
    bool Contains(const Key& key) const;
};

class Registry {
public:
    explicit Registry(const char* name, bool formatting)
        : formatting_{formatting}, name_{name} {
        if (formatting_) {
            count_ = 1;
        }
    }
    ~Registry() { count_ = 0; }
    void lock() const {}
    bool operator==(const Registry& other) const { return name_ == other.name_; }
    names::level_enum level() const;

private:
    bool formatting_;
    const char* name_;
    int count_ = 0;
};

template <typename Key, class Compare>
inline bool SkipList<Key, Compare>::Contains(const Key& key) const {
    return key == key;
}

template <bool B = false> constexpr auto count() -> int { return B ? 1 : 0; }

inline names::level_enum Registry::level() const {
    return level::on;
}

}  // namespace store

WARNINGS_POP_()  // a macro's call at the margin, then a directive
#if 1
namespace other {
int answer() { return 42; }
}
#endif
