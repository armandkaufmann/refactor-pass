public class Bag {
    private int size;

    public int size() { return size; }

    @Override
    public String toString() { return "Bag(" + size + ")"; }

    record Item(String name) {
        Item {
            name = name.trim();
        }
    }
}
