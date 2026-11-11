res.send = function send(body) {
  return body
}
Foo.prototype.bar = async function (a, b) {
  return a + b
}
window.fetch = (
  input: RequestInfo,
  init?: RequestInit,
): Promise<Response> => {
  return real(input, init)
}
class Store {
  constructor() {
    this.handler = (event) => {
      return event
    }
  }
  fetch: (
    request: Request,
  ) => Promise<Response> = (request) => {
    return go(request)
  }
  private readonly onEvent: (
    event: Event,
  ) => void = (event) => {
    log(event)
  }
}
// Not functions: an anonymous callback passed to a call, values that aren't functions, a comparison.
app.handler = wrap((req) => {
  return req
})
a.b = c
a.b = (x + y) * 2
x.y = foo(
  a,
)
x.y == (z) => z
