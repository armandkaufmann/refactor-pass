class Request
  HEADER = /\s*[\w.]+=(?:[\w.]+|"(?:[^"\\]|\\.)*")?\s*/
  VALUE = %r{(?:\w+|\*)/(?:\w+|\*)(?:\s*;\s*#{HEADER})*}
  WORDS = %w[a ( b]

  def accept
    @env['HTTP_ACCEPT'].to_s.scan(VALUE).map { |e| e.split /;/ }
  end

  def quoted(text)
    text.gsub(/[";,]/) { |c| "\\#{c}" } % [1]
  end

  def heredoc
    <<~TEXT
}
def not_a_method
    TEXT
  end

  def at_the_margin
<<-'end;'
  def neither
end;
  end

  def interpolated(h)
    "#{h["key"]} and #{h['other']}"
  end

  def globals
    [$", $', ?"]
  end

=begin
  def commented_out
  end
=end

  def last
    1
  end
end
__END__
def data_not_code
