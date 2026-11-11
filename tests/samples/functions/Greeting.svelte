<script>
  export let name = 'world';

  function greet(person) {
    return `Hello ${person}!`;
  }

  const shout = (text) => text.toUpperCase();
</script>

<h1>{greet(name)}</h1>
<p>{shout(name)}</p>
