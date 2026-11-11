// Definitions outside their classes, indented inside a namespace, and calls that look like them.
namespace Catch {
    struct Pair { int first; int second; };
    Pair pair() { return Pair{1, 2}; }
    int tie(int& a, int& b) { return a + b; }

    class Session {
    public:
        Session();
        ~Session();
        int run(int argc);
        static int helper(int n) { return n; }
        static int& slot() { static int s; return s; }

    private:
        bool alive;
        int code;
    };

    Session::Session() {
        alive = true;
    }

    Session::~Session() {
        alive = false;
    }

    int
    Session::run( int argc ) {
        return argc;
    }

    class Config {
    public:
        explicit Config(int data);

    private:
        int m_data;
    };

    Config::Config( int data ):
        m_data( data ) {
        m_data += 1;
    }

    class Version {
    public:
        Version(int major, int minor);

    private:
        int m_major;
    };

    Version::Version
        (   int major,
            int minor )
    :   m_major( major + minor )
    {}

    int use() {
        int a = Session::helper(1);
        int b = tie(a, a);
        Session::slot() =
            a + b;
        Pair p{
            Session::helper(a),
            Pair{b, b}.first};
        return Session::helper(
            Session::helper(p.first),
            b);
    }
}
