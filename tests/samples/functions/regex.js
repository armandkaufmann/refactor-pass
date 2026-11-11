const isValidHeaderName = (str) => /^[-_a-zA-Z0-9^`|~,!#$%&'*+.]+$/.test(str.trim());
function kind(x) {
  switch (typeof x) {
    case 'string':
      return /["'`]/.test(x)
  }
  if (typeof /a/ === 'object') throw /b`/
  const y = await /c'/.exec(x)
  return x / 2 / 3
}
const half = (n) => n / 2;
function after() {
  return 1
}
