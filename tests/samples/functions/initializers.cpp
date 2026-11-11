Cart::Cart(int size)
    : sum_(size)
    , count_(0) {
}

int Cart::total() const {
    return sum_;
}

::std::string Cart::name() const {
    return "cart";
}
