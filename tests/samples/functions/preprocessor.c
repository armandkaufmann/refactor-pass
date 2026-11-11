#include <stdio.h>

#define SWAP(a, b) { int t = a; \
    a = b; b = t; }

#ifdef _WIN32
int umain(int argc, char **argv) {
#else
int main(int argc, char **argv) {
#endif
    return run(argc, argv);
}

static int scan(const char *fmt)
{
    int c;
again:  switch (c = *fmt++) {
    case '%':
        goto again;
    }
    return c;
}

 double
strtod_like
 (const char *s)
{
    return 0;
}

static int twice(int x) { return x * 2; }
