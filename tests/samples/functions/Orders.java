package shop;

import java.util.List;

public class Orders implements Loader {
    private final Repo repo;

    Orders(Repo repo) {
        this.repo = repo;
    }

    @Override
    public ResponseEntity<Map<String, Object>> longOne(
            @RequestParam("a") int a,
            @Valid Foo b) throws IOException {
        if (a > 0) {
            return null;
        }
        return ok(
            a,
            b);
    }

    public static <T> List<T> listOf(T item) {
        return List.of(item);
    }

    private int[] numbers() {
        return new int[] {1, 2};
    }
}

interface Loader {
    Order load(int id) throws IOException;
}
