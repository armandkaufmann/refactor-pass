#include <string>

class Cache {
 public:
  Cache()
      : size_(0),
        hits_(0) {
  }
  explicit Cache(int size) : size_(size) {}
  virtual ~Cache() {
    clear();
  }
  int size() const { return size_; }
  bool operator==(const Cache& other) const {
    return size_ == other.size_;
  }
  operator bool() const { return size_ > 0; }
  Cache& operator=(const Cache&) = default;
  void clear()
      EXCLUSIVE_LOCKS_REQUIRED(mu_) {
    size_ = 0;
  }

 private:
  int size_;
  int hits_;
};

extern "C" int c_entry(int x) {
  return x;
}

const char* pattern() {
  return R"(a "quoted" {brace)";
}
