using System.Threading.Tasks;

namespace Store
{
    public readonly struct Money
    {
        public long Cents { get; }

        public void delete()
        {
            System.Console.WriteLine(Cents);
        }

        public Task await() => Task.CompletedTask;

        public static Money operator +(Money a, Money b)
        {
            return new Money();
        }

        public static implicit operator long(Money m) => m.Cents;

        public string Describe(string label)
        {
            return $"{label}: {(Cents > 0 ? "}credit" : "debit{")} {{total}}";
        }

        public void After()
        {
        }
    }
}
