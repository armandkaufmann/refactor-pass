namespace Shop;

public class Orders
{
    private readonly Repo _repo;

    public Orders(Repo repo)
    {
        _repo = repo;
    }

    public async Task<IActionResult> Load(
        [FromBody] Query query,
        CancellationToken ct = default)
    {
        var order = await _repo.Find(query.Id, ct);
        return Ok(order);
    }

    public int Double(int a) => a * 2;

    private static (int, string) Pair(int a)
    {
        return (a, "}");
    }

    public string Name { get; set; }
}

public interface IRepo
{
    Task<Order> Find(int id, CancellationToken ct);
}
