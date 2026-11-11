export default async function* (pages) {
  for await (const page of pages) yield page
}
