import java.util.List;

class Annotated {
    @Override public String toString() {
        return "annotated";
    }

    @SuppressWarnings("unchecked") @Deprecated
    public <T> List<T> cast(List<?> list) {
        return (List<T>) list;
    }

    @Test void parsesEmptyInput() {
        assertEquals(0, parse("").size());
    }

    @Inject Annotated(String name) {
        this.name = name;
    }

    private String name;
}
