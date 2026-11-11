class Orders
  def initialize(repo)
    @repo = repo
  end

  def total = @repo.sum
end

class Cart
  def size; @items.size; end
end
