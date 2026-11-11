#include <vector>

namespace shop {

class Cart {
public:
    explicit Cart(int size);
    ~Cart();
    int total() const {
        return sum_;
    }
private:
    int sum_ = 0;
};

Cart::Cart(int size) : sum_(size) {
}

Cart::~Cart() {
    sum_ = 0;
}

std::vector<int> split(const std::string& text,
                       char sep) {
    std::vector<int> out;
    for (char c : text) {
        if (c == sep) out.push_back(1);
    }
    return out;
}

}  // namespace shop
