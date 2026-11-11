export function arrow(statements: number, body: string) {
  return [
    `${statements > 1 ? `{` : `(`} =>`,
    body,
    statements > 1 ? `}` : `)`,
  ]
}
function after() {
  return 1
}
