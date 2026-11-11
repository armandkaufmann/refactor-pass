<template>
  <button @click="save">Save</button>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const count = ref(0)

function save() {
  count.value++
}

const reset = () => {
  count.value = 0
}
</script>
