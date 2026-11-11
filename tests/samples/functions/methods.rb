class Bag
  def [](key)
    @items[key]
  end

  def []=(key, value)
    @items[key] = value
  end

  def <<(item)
    @items << item
  end

  def ==(other)
    other.is_a?(Bag)
  end

  def -@
    self
  end

  private def secret
    42
  end

  def self.schedule(*) yield end
  def @@cache.flush(*) end

  def load(path)
    File.read(path)
  rescue Errno::ENOENT
    nil
  else
    :ok
  ensure
    close
  end
end

Holder = Class.new do
  def initialize(app) @app = app end
  def call(env) @app.call(env) end
end

run(Class.new {
  def each
    yield 1
  end
})
