using System;

namespace Logging
{
    public sealed class NullScope
    {
        public T Get<T>(string key) where T : class => null;

        public IDisposable BeginScope<TState>(TState state) where TState : notnull => null;

        public T Make<T>() where T : class, new() => new T();

        public void After()
        {
        }
    }
}
