# The methods Ruby's own parser finds in a repo's Ruby files, as JSON: {path: [[name, first line, last line], ...]},
# for def and def self.x, from def to end. Files are parsed, never run; one this Ruby can't parse is left out.
# Needs Ruby 2.6 or later, for RubyVM::AbstractSyntaxTree. Usage: ruby rb_truth.rb REPO FOLDER...
require 'json'

def walk(node, found)
  return unless node.is_a?(RubyVM::AbstractSyntaxTree::Node)
  case node.type
  when :DEFN then found << [node.children[0].to_s, node.first_lineno, node.last_lineno]
  when :DEFS then found << [node.children[1].to_s, node.first_lineno, node.last_lineno]
  end
  node.children.each { |child| walk(child, found) }
end

repo = File.expand_path(ARGV[0])
out = {}
$stderr.reopen(File::NULL) # The parser's warnings about the files.
ARGV[1..-1].each do |folder|
  Dir.glob(File.join(repo, folder, '**', '*.rb')).sort.each do |path|
    path = File.expand_path(path)
    next if File.symlink?(path) || !File.file?(path)
    begin
      root = RubyVM::AbstractSyntaxTree.parse(File.read(path))
    rescue SyntaxError, StandardError
      next
    end
    found = []
    walk(root, found)
    out[path[(repo.length + 1)..-1]] = found
  end
end
print JSON.generate(out)
