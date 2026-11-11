extends Node

signal done

func short(a):
	return a

static func make() -> Node:
	return Node.new()

func long_one(
		a: int,
		b: int,
) -> int:
	var x = a + b
	# a comment
	if x > 0:
		x += 1
	return x

func _ready():
	done.emit()
