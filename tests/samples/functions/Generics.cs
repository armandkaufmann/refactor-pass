using System;
using System.Threading.Tasks;

namespace Samples
{
    public sealed class Reader : IAsyncDisposable, IDisposable
    {
        public static T Deserialize<T>(string value)
        {
            return default!;
        }

        public void Add<TKey, TValue>(TKey key, TValue value) where TKey : notnull
        {
            Console.WriteLine(key);
        }

        [Obsolete("use Deserialize")] public static T Get<T>(string key) => Deserialize<T>(key);

        ValueTask IAsyncDisposable.DisposeAsync()
        {
            return default;
        }

        void IDisposable.Dispose() => Console.WriteLine("disposed");
    }
}
