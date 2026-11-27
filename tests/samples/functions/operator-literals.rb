# Operators' names that open a literal elsewhere; a literal after when, return, unless or a tab.
class A
  def self.`(cmd)
    1
  end
end

def g
  "a"
end
class A
  def /(o)
    "a"
  end
end

def g
  "a"
end
class A
  def x; y = %w[" a]; end
end

def g
  "a"
end
class A
  undef `
end

def g
  "a"
end
class A
  def @x.`(cmd)
    1
  end
end

def g
  "a"
end
def f(s)
  x =	/"/ =~ s
  y = 1
end

def g
  "a"
end
def f(s)
  return / "/ =~ s
end

def g
  "a"
end
def f(s)
  x = s.scan(
/"/)
end

def g
  "a"
end
def f(s)
  unless / "/ =~ s
    1
  end
end

def g
  "a"
end
def f
  x = [
?"
  ]
end

def g
  "a"
end
def f(c)
  case c
  when ?"
    1
  end
end

def g
  "a"
end
