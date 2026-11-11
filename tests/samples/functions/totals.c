#include <stdio.h>

static int
long_one(int a,
         int b)
{
    int x = a + b;
    /* a brace in a comment { */
    return x;
}

int main(int argc, char **argv) {
    printf("%s\n", "}");
    return long_one(1,
                    2);
}

void declared(int a);
