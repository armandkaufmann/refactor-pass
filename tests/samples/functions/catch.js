function load() {
  try
  {
    run()
  }
  catch(e)
  {
    report(e)
  }
}
class Filter {
  constructor() {}
  catch(exception, host) {
    return host
  }
  delete (key) {
    return key
  }
}
