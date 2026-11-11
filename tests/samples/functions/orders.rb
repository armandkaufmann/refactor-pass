class Orders
  def initialize(repo)
    @repo = repo
  end

  def self.build
    new(Repo.new)
  end

  def long_one(a,
               b,
               c)
    # a comment
    x = a + b + c
    x
  end

  def kw(
    a:,
    b: 2
  )
    a + b
  end

  def valid?
    true
  end
end
