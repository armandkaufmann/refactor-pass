function add(a, b) {
  return a + b;
}

async function* pages(client) {
  yield* client.all();
}

class Cart {
  static create() {
    return new Cart();
  }

  get size() {
    return this.items.length;
  }

  set size(value) {
    this.items.length = value;
  }

  async #load(id) {
    return fetch(id);
  }

  *[Symbol.iterator]() {
    yield* this.items;
  }
}

const helpers = {
  double(x) {
    return x * 2;
  },
  triple: function (x) {
    return x * 3;
  },
  half: x => x / 2,
};

const square = function (x) {
  return x * x;
};
