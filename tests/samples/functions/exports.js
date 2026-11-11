module.exports = function (req, res) {
  let x = 1;
  return x;
};
exports.handler = async (event) => {
  let x = 1;
  return x;
};
module.exports.parse = function parse(text) {
  return JSON.parse(text);
};
exports.one = x => x + 1;
