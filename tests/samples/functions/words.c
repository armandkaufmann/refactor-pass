/* Words other languages reserve are names in C. */
struct node { int id; };

static struct node *new(int id)
{
    return 0;
}

static void delete(struct node *n)
{
    n->id = 0;
}

int foreach(int (*visit)(int), int n) {
    return visit(n);
}

static int class(void) { return 1; }

void (* const handlers[])(void) = { 0 };
