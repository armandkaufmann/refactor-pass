class Lines {
  next() {
    return { done: true };
  }

  return(value) {
    return { done: true, value };
  }

  throw(error) {
    throw error;
  }
}

const reader = {
  delete() {
    return 0;
  },
  return() {
    return 1;
  },
};

for (let n = 0; n < 2; n++) {
  {
    for (let i = 0; i < n; i++) {
      console.log(i, reader);
    }
  }
}
