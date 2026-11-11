namespace Shop;

public class SpecialOrders : Orders
{
    public SpecialOrders(Repo repo)
        : base(repo)
    {
    }

    public SpecialOrders(Repo repo, int limit)
        : this(repo)
    {
        Limit = limit;
    }
}
