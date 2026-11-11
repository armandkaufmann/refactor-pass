import java.io.File;
import java.io.IOException;

abstract class Walker {
    protected final void checkIfCancelled(final File file, final int depth) throws
            IOException {
        if (handleIsCancelled(file, depth)) {
            throw new IOException("cancelled");
        }
    }

    protected abstract boolean handleIsCancelled(File file, int depth) throws
            IOException;

    void after() {
    }
}
