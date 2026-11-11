import java.io.File;

class TemporaryFolder {
    private File root;

    public void delete() {
        root.delete();
    }

    public int foreach(int n) {
        return n;
    }

    synchronized void print(String text) {
        System.out.println(text);
    }

    String get$Value() { return "value"; }

    boolean await() { return true; }
}
