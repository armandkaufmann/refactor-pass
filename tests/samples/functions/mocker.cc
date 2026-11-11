// Function types in type arguments, a qualifier on the line after the parameters, and initializers that a
// directive or a macro interrupts.
#define LOCKS_REQUIRED(mu)
#define WARNINGS_PUSH(n)
#define WARNINGS_POP()

template <typename F> class function {};
struct Mutex {};
Mutex g_mutex;

template <typename F> class Mocker;

template <typename R, typename... Args>
class Mocker<R(Args...)> {
 public:
  function<R(Args...)> AsFunction() {
    return function<R(Args...)>();
  }
  R Invoke(Args... args);
  int Find(int key)
      const LOCKS_REQUIRED(g_mutex) {
    return key;
  }
};

template <typename R, typename... Args>
R Mocker<R(Args...)>::Invoke(Args... args) {
  return R();
}

class Stream {
 public:
  explicit Stream(int fd)
      : fd_(fd),
#ifdef _WIN32
        copy_(fd + 1)
#else
        copy_(fd)
#endif
  {
    fd_ = copy_;
  }

 private:
  int fd_;
  int copy_;
};

class Impl {
 public:
  explicit Impl(int* parent);

 private:
  int* parent_;
  int reporter_;
  int other_;
};

Impl::Impl(int* parent)
    : parent_(parent),
      WARNINGS_PUSH(4355)
          reporter_(0),
      WARNINGS_POP() other_(1) {
}
