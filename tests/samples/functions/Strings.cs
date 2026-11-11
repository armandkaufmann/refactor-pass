[assembly: InternalsVisibleTo("Shop.Tests")]

namespace Shop;

public class Reader
{
    public string Escape(char c)
    {
        return @"\" + c;
    }

    public string Json()
    {
        return @"{
  ""name"": ""value"" (";
    }

    public int Size() { return _items.Count; }

#if HAVE_ASYNC
    public async Task Load(string path)
    {
#else
    public void Load(string path)
    {
#endif
        _items.Clear();
    }
}

public class Action(int id) : IDisposable
{
    public void Dispose() { }
}

public record Point(int X, int Y) { }
